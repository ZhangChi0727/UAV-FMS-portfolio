"""CODEBRIM original VOC XML -> multilabel YOLO detection data.

Missing XML is NOT a negative label. Default execution stops if any are missing;
--exclude-unannotated explicitly excludes and records those images. Image-level
splitting is not bridge-disjoint evaluation. Exact duplicate bytes share a split.
VOC one-based inclusive boxes become zero-based half-open pixel boxes.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
from io import BytesIO
import json
from pathlib import Path
import random
import shutil
import struct
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image
import yaml

CLASSES = ('crack', 'spallation', 'efflorescence', 'exposed_bar', 'corrosion_stain')
FLAGS = ('Crack', 'Spallation', 'Efflorescence', 'ExposedBars', 'CorrosionStain')
EDGE = Path(__file__).resolve().parents[1]
OFFICIAL_MD5 = '27baf3a036d0b7d757ff4df47c08c449'


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def stored_orientation(data):
    """Set the primary JPEG EXIF orientation tag to 1 in place (no re-encoding).

    Only two bytes change. APP segment sizes and MPO secondary-view offsets stay
    intact. Boxes remain in the XML's stored-raster coordinate system.
    """
    buffer = bytearray(data)
    offset = 2
    while offset + 4 < len(buffer) and buffer[offset] == 0xff:
        marker = buffer[offset + 1]
        if marker in (0xda, 0xd9):
            break
        length = int.from_bytes(buffer[offset+2:offset+4], 'big')
        if length < 2 or offset + 2 + length > len(buffer):
            raise ValueError('invalid JPEG segment')
        if marker == 0xe1 and buffer[offset+4:offset+10] == b'Exif\x00\x00':
            base = offset + 10
            endian = '<' if buffer[base:base+2] == b'II' else '>'
            if buffer[base:base+2] not in (b'II', b'MM'):
                raise ValueError('invalid EXIF byte order')
            directory = base + struct.unpack_from(endian+'I', buffer, base+4)[0]
            count = struct.unpack_from(endian+'H', buffer, directory)[0]
            for index in range(count):
                entry = directory + 2 + 12*index
                if entry + 12 > offset + 2 + length:
                    raise ValueError('EXIF directory outside APP1 segment')
                tag, kind, size = struct.unpack_from(endian+'HHI', buffer, entry)
                if tag == 274:
                    if kind != 3 or size != 1:
                        raise ValueError('unsupported orientation encoding')
                    struct.pack_into(endian+'H', buffer, entry+8, 1)
                    return bytes(buffer)
        offset += 2 + length
    raise ValueError('primary EXIF orientation entry not found')


def copy_image(source, target):
    """Normalize JPEG tail/EXIF metadata, proving stored-raster pixels identical."""
    with Image.open(source) as im:
        image_format = im.format
        orientation = im.getexif().get(274, 1)
        source_size = im.size
    if orientation not in range(1, 9):
        raise ValueError('invalid EXIF orientation')
    data = Path(source).read_bytes()
    cleaned = data
    removed = 0
    if image_format == 'JPEG':
        if not data.endswith(b'\xff\xd9'):
            end = data.rfind(b'\xff\xd9') + 2
            if end < 2:
                raise ValueError('JPEG lacks end marker')
            cleaned = data[:end]
            removed = len(data) - end
    if orientation != 1:
        cleaned = stored_orientation(cleaned)
    pixel_hash = None
    if cleaned != data:
        import cv2
        import numpy as np
        flags = cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION
        before = cv2.imdecode(np.frombuffer(data, np.uint8), flags)
        after = cv2.imdecode(np.frombuffer(cleaned, np.uint8), cv2.IMREAD_COLOR)
        if before is None or after is None or not np.array_equal(before, after):
            raise ValueError('metadata normalization changed stored-raster pixels')
        if (after.shape[1], after.shape[0]) != source_size:
            raise ValueError('normalized decoder dimensions differ from XML raster')
        with Image.open(BytesIO(cleaned)) as im:
            if im.getexif().get(274,1) != 1:
                raise ValueError('orientation normalization failed')
        pixel_hash = hashlib.sha256(before.tobytes()).hexdigest()
        Path(target).write_bytes(cleaned)
    else:
        shutil.copy2(source, target)
    return {'encoded_format': image_format, 'post_eoi_bytes_removed': removed,
            'source_exif_orientation': orientation, 'prepared_exif_orientation': 1,
            'pixel_preserving_normalization': cleaned != data,
            'verified_stored_raster_bgr_sha256': pixel_hash}


def parse_xml(path, collect_unknown=False):
    root = ET.parse(path).getroot()
    name = root.findtext('filename')
    if not name or Path(name).name != name or '\\' in name:
        raise ValueError('annotation filename must be a basename')
    w, h = (int(root.findtext(f'size/{key}')) for key in ('width', 'height'))
    if min(w, h) <= 0:
        raise ValueError('nonpositive image dimensions')
    rows, clamped, background, unknown = [], 0, 0, []
    for object_index, obj in enumerate(root.findall('object')):
        flags = []
        for key in ('Background', *FLAGS):
            value = obj.findtext(f'Defect/{key}')
            if value not in ('0', '1'):
                raise ValueError(f'missing or invalid Defect/{key}')
            flags.append(int(value))
        if (not any(flags) and not collect_unknown) or (flags[0] and any(flags[1:])):
            raise ValueError('ambiguous background/defect flags')
        raw = [int(obj.findtext(f'bndbox/{key}')) for key in ('xmin', 'ymin', 'xmax', 'ymax')]
        x1, y1, x2, y2 = raw[0] - 1, raw[1] - 1, raw[2], raw[3]
        box = [max(0, min(w, x1)), max(0, min(h, y1)), max(0, min(w, x2)), max(0, min(h, y2))]
        clamped += box != [x1, y1, x2, y2]
        x1, y1, x2, y2 = box
        if x2 <= x1 or y2 <= y1:
            raise ValueError('degenerate box after clipping')
        if not any(flags):
            unknown.append({'object_index': object_index, 'voc_box': raw, 'flags': flags})
            continue
        if flags[0]:
            background += 1
            continue
        normalized = ((x1+x2)/(2*w), (y1+y2)/(2*h), (x2-x1)/w, (y2-y1)/h)
        assert all(0 <= v <= 1 for v in normalized)
        rows.extend((i, *normalized) for i, flag in enumerate(flags[1:]) if flag)
    return {'filename': name, 'width': w, 'height': h, 'rows': rows,
            'clamped_objects': clamped, 'background_objects': background, 'unknown_objects': unknown}


def split_groups(groups, seed=42):
    """Keys identify independent image groups; callers group byte duplicates first."""
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    n = len(keys)
    cuts = (int(.8*n), int(.9*n))
    return {split: sorted(item for key in selected for item in groups[key])
            for split, selected in zip(('train', 'val', 'test'),
                                       (keys[:cuts[0]], keys[cuts[0]:cuts[1]], keys[cuts[1]:]))}


def extract_original(archive, destination):
    """Verify official archive and CRC during streaming; no existing files replaced."""
    md5 = digest(archive, 'md5')
    if md5 != OFFICIAL_MD5:
        raise ValueError(f'official MD5 mismatch: {md5}')
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as z:
        # This MD5-locked official >4-GiB archive has mixed-width offsets.
        # Python adds 2**32 to some early entries. Adjust only a missing header
        # whose exact -2**32 position has the local-file signature. ZipFile.open
        # subsequently checks each filename, and streamed reads check its CRC.
        corrected = 0
        with Path(archive).open('rb') as source:
            for info in z.infolist():
                source.seek(info.header_offset)
                if source.read(4) == b'PK\x03\x04':
                    continue
                candidate = info.header_offset - 2**32
                if candidate < 0:
                    raise zipfile.BadZipFile('unrecoverable local header')
                source.seek(candidate)
                if source.read(4) != b'PK\x03\x04':
                    raise zipfile.BadZipFile('unexpected offset; refusing generic repair')
                info.header_offset = candidate
                corrected += 1
        # Recompute overlap guards after correcting the in-memory offsets.
        end = z.start_dir
        for info in sorted(z.infolist(), key=lambda item: item.header_offset, reverse=True):
            if hasattr(info, '_end_offset'):  # Present in newer CPython ZIP readers.
                info._end_offset = end
            end = info.header_offset
        for info in z.infolist():
            if not info.filename.startswith('original_dataset/') or info.is_dir():
                continue
            if not info.filename.lower().endswith(('.xml', '.jpg')):
                continue
            target = (destination / info.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('unsafe archive path')
            if target.exists():
                raise FileExistsError(f'refusing to overwrite extraction: {target}')
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst)
    return {'archive': str(Path(archive).resolve()), 'md5': md5,
            'official_source': 'https://zenodo.org/records/2620293', 'crc': 'verified during extraction',
            'in_memory_4GiB_offset_corrections': corrected, 'archive_modified': False}


def prepare(raw, output, exclude_unannotated=False, exclude_ambiguous=False,
            exclude_dimension_mismatch=False):
    raw, output = Path(raw), Path(output)
    if output.exists():
        raise FileExistsError(f'refusing to replace dataset: {output}')
    images = {p.name: p for p in (raw / 'images').glob('*.jpg')}
    annotations = {}
    for path in sorted((raw / 'annotations').glob('*.xml')):
        parsed = parse_xml(path, collect_unknown=True)
        name = parsed['filename']
        if name in annotations or name not in images:
            raise ValueError(f'duplicate annotation or missing image: {name}')
        parsed['xml_sha256'] = digest(path)
        annotations[name] = parsed
    if not images or not annotations:
        raise ValueError('no images or XML found')
    missing = sorted(images.keys() - annotations.keys())
    ambiguous = {name: p['unknown_objects'] for name, p in annotations.items() if p['unknown_objects']}
    dimension_mismatches, decode_errors, groups = {}, {}, defaultdict(list)
    for name, parsed in annotations.items():
        try:
            with Image.open(images[name]) as im:
                if im.size != (parsed['width'], parsed['height']):
                    dimension_mismatches[name] = {'image': list(im.size),
                                                 'xml': [parsed['width'], parsed['height']]}
                im.load()  # Full decode, not just a header check.
        except OSError as exc:
            decode_errors[name] = str(exc)
        parsed['image_sha256'] = digest(images[name])
        groups[parsed['image_sha256']].append(name)
    conflicting_duplicates = [group for group in groups.values()
                              if len({tuple(annotations[n]['rows']) for n in group}) != 1]
    audit = {'images': len(images), 'xml': len(annotations), 'missing_xml': missing,
             'ambiguous_xml': ambiguous,
             'dimension_mismatches': dimension_mismatches, 'decode_errors': decode_errors,
             'exact_duplicate_groups': [g for g in groups.values() if len(g) > 1],
             'conflicting_duplicate_groups': conflicting_duplicates,
             'missing_xml_semantics': 'unknown, NOT negative',
             'host_type': 'development-host'}
    write_json(raw.parent / 'annotation_audit.json', audit)
    if missing and not exclude_unannotated:
        raise ValueError(f'{len(missing)} images lack XML; see annotation_audit.json; explicit exclusion required')
    if ambiguous and not exclude_ambiguous:
        raise ValueError(f'{len(ambiguous)} images contain unlabeled objects; explicit exclusion required')
    if dimension_mismatches and not exclude_dimension_mismatch:
        raise ValueError(f'{len(dimension_mismatches)} XML/image dimensions differ; explicit exclusion required')
    if decode_errors or conflicting_duplicates:
        raise ValueError('image decode errors or conflicting duplicate labels; see annotation_audit.json')
    annotations = {n: p for n, p in annotations.items() if n not in ambiguous and n not in dimension_mismatches}
    groups = {k: [n for n in names if n in annotations] for k, names in groups.items()}
    groups = {k: names for k, names in groups.items() if names}
    splits = split_groups(groups)
    manifest = {'seed': 42, 'classes': CLASSES, 'raw': str(raw.resolve()),
                'inclusion_note': f'{len(annotations):,} annotated images included; {len(missing)} images without XML excluded (unannotated for object detection, not treated as verified negatives)',
                'grouping': 'image bytes (exact duplicates grouped); NOT bridge-disjoint',
                'coordinate_convention': 'VOC 1-based inclusive -> zero-based half-open -> YOLO',
                'excluded_missing_xml': missing, 'splits': {}, 'images': {}}
    manifest['excluded_ambiguous_xml'] = ambiguous
    manifest['excluded_dimension_mismatch'] = dimension_mismatches
    manifest['original_xml_inventory_note'] = '1,052 annotated images included; 538 images without XML excluded (unannotated for object detection, not treated as verified negatives)'
    manifest['original_xml_inventory_note_scope'] = 'Initial XML-present inventory only, superseded by explicit per-image quality exclusions and final included counts above.'
    for split, names in splits.items():
        counts = Counter()
        for folder in ('images', 'labels'):
            (output / folder / split).mkdir(parents=True, exist_ok=True)
        for name in names:
            p = annotations[name]
            target = output / 'images' / split / name
            normalization = copy_image(images[name], target)
            p['source_image_sha256'] = p['image_sha256']
            p['image_sha256'] = digest(target)
            p.update(normalization)
            text = ''.join(f'{r[0]} ' + ' '.join(f'{v:.10f}' for v in r[1:]) + '\n' for r in p['rows'])
            label_path = output / 'labels' / split / (Path(name).stem + '.txt')
            label_path.write_text(text, encoding='utf-8')
            counts.update(r[0] for r in p['rows'])
            manifest['images'][name] = {**{k: v for k, v in p.items() if k != 'rows'},
                                        'split': split, 'label_sha256': digest(label_path)}
        manifest['splits'][split] = {'files': names, 'image_count': len(names),
            'empty_labels': sum(not annotations[n]['rows'] for n in names),
            'class_counts': {c: counts[i] for i, c in enumerate(CLASSES)},
            'file_list_sha256': hashlib.sha256(('\n'.join(names)+'\n').encode()).hexdigest()}
    config = {'path': str(output.resolve()).replace('\\', '/'),
              'train': 'images/train', 'val': 'images/val', 'test': 'images/test',
              'names': dict(enumerate(CLASSES))}
    (output / 'dataset.yaml').write_text(yaml.safe_dump(config, sort_keys=False), encoding='utf-8')
    manifest['dataset_yaml_sha256'] = digest(output / 'dataset.yaml')
    write_json(output / 'split_manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='verify MD5 and extract first (once only)')
    parser.add_argument('--raw', type=Path, default=EDGE / 'data/codebrim_raw/original_dataset')
    parser.add_argument('--output', type=Path, default=EDGE / 'data/codebrim_yolo')
    parser.add_argument('--exclude-unannotated', action='store_true')
    parser.add_argument('--exclude-ambiguous', action='store_true', help='explicitly exclude whole images with unknown object labels')
    parser.add_argument('--exclude-dimension-mismatch', action='store_true')
    args = parser.parse_args()
    if args.archive:
        receipt = extract_original(args.archive, args.raw.parent)
        write_json(args.raw.parent / 'extraction.json', receipt)
        print(json.dumps(receipt), flush=True)
    result = prepare(args.raw, args.output, args.exclude_unannotated, args.exclude_ambiguous,
                     args.exclude_dimension_mismatch)
    print(json.dumps({k: {field: value for field, value in v.items() if field != 'files'}
                      for k, v in result['splits'].items()}, indent=2))


if __name__ == '__main__':
    main()
