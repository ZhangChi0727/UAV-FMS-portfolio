import json
from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_codebrim import FLAGS, copy_image, parse_xml, prepare, split_groups


def xml_file(tmp_path, name='one.jpg', box=(1, 1, 100, 50), positive=('Crack', 'Spallation')):
    flags = ''.join(f'<{k}>{int(k in positive)}</{k}>' for k in ('Background', *FLAGS))
    bounds = ''.join(f'<{k}>{v}</{k}>' for k, v in zip(('xmin','ymin','xmax','ymax'), box))
    path = tmp_path / (Path(name).stem + '.xml')
    path.write_text(f'<annotation><filename>{name}</filename><size><width>100</width><height>50</height></size>'
                    f'<object><bndbox>{bounds}</bndbox><Defect>{flags}</Defect></object></annotation>')
    return path


def test_multilabel_and_voc_full_image(tmp_path):
    result = parse_xml(xml_file(tmp_path))
    assert result['rows'] == [(0, .5, .5, 1., 1.), (1, .5, .5, 1., 1.)]


def test_jpeg_padding_normalization_preserves_pixels(tmp_path):
    import cv2
    import numpy as np
    source, target = tmp_path / 'source.jpg', tmp_path / 'target.jpg'
    Image.new('RGB', (12,10), 'red').save(source)
    source.write_bytes(source.read_bytes() + b'padding\x00\x00')
    original = source.read_bytes()
    receipt = copy_image(source,target)
    assert receipt['post_eoi_bytes_removed'] == 9
    assert np.array_equal(cv2.imread(str(source)), cv2.imread(str(target)))
    assert target.read_bytes().endswith(b'\xff\xd9')
    assert source.read_bytes() == original


@pytest.mark.parametrize('orientation',[3,6,8])
def test_exif_normalization_preserves_xml_raster(tmp_path,orientation):
    import cv2
    import numpy as np
    source, target = tmp_path / 'source.jpg', tmp_path / 'target.jpg'
    image = Image.new('RGB',(20,10),'red')
    exif = image.getexif()
    exif[274] = orientation
    image.save(source,exif=exif)
    receipt = copy_image(source,target)
    before = cv2.imread(str(source),cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    after = cv2.imread(str(target))
    assert after.shape == (10,20,3)
    assert np.array_equal(before,after)
    assert receipt['source_exif_orientation'] == orientation
    with Image.open(target) as im:
        assert im.getexif()[274] == 1


def test_clamping(tmp_path):
    result = parse_xml(xml_file(tmp_path, box=(-5, -3, 500, 600)))
    assert result['clamped_objects'] == 1
    assert all(0 <= v <= 1 for r in result['rows'] for v in r[1:])
    assert result['rows'][0][1:] == (.5, .5, 1., 1.)


def test_background_empty_label(tmp_path):
    assert parse_xml(xml_file(tmp_path, positive=('Background',)))['rows'] == []


@pytest.mark.parametrize('positive', [(), ('Background','Crack')])
def test_unknown_or_conflicting_flags_rejected(tmp_path, positive):
    with pytest.raises(ValueError):
        parse_xml(xml_file(tmp_path, positive=positive))


def test_invalid_box_rejected(tmp_path):
    with pytest.raises(ValueError):
        parse_xml(xml_file(tmp_path, box=(101, 1, 102, 4)))


def test_unknown_objects_never_become_background(tmp_path):
    raw = tmp_path / 'raw'
    (raw / 'images').mkdir(parents=True)
    (raw / 'annotations').mkdir()
    for name, color, flags in [('one.jpg','white',('Crack',)), ('unknown.jpg','black',())]:
        Image.new('RGB', (100,50), color).save(raw / 'images' / name)
        xml_file(raw / 'annotations', name=name, positive=flags)
    with pytest.raises(ValueError, match='unlabeled objects'):
        prepare(raw, tmp_path / 'out')
    result = prepare(raw, tmp_path / 'out', exclude_ambiguous=True)
    assert list(result['images']) == ['one.jpg']
    assert list(result['excluded_ambiguous_xml']) == ['unknown.jpg']


def test_wrong_dimensions_not_silently_rescaled(tmp_path):
    raw = tmp_path / 'raw'
    (raw / 'images').mkdir(parents=True)
    (raw / 'annotations').mkdir()
    for name, dims in [('one.jpg',(100,50)), ('wrong.jpg',(120,60))]:
        Image.new('RGB', dims, 'white').save(raw / 'images' / name)
        xml_file(raw / 'annotations', name=name)
    with pytest.raises(ValueError, match='dimensions differ'):
        prepare(raw, tmp_path / 'out')
    result = prepare(raw, tmp_path / 'out', exclude_dimension_mismatch=True)
    assert list(result['images']) == ['one.jpg']
    assert result['excluded_dimension_mismatch']['wrong.jpg'] == {'image':[120,60],'xml':[100,50]}


def test_deterministic_image_group_split():
    groups = {str(i): [f'image{i}.jpg'] for i in range(100)}
    split = split_groups(groups)
    assert split == split_groups(dict(reversed(list(groups.items()))), 42)
    assert [len(v) for v in split.values()] == [80, 10, 10]
    assert len(set(sum(split.values(), []))) == 100
    groups['0'].append('duplicate.jpg')
    split = split_groups(groups)
    assert any('image0.jpg' in names and 'duplicate.jpg' in names for names in split.values())


def test_approved_day1_split_counts():
    split = split_groups({str(i): [f'{i}.jpg'] for i in range(1040)}, seed=42)
    assert [len(split[s]) for s in ('train','val','test')] == [832,104,104]


def test_missing_xml_not_background_and_manifest(tmp_path):
    raw = tmp_path / 'raw'
    (raw / 'images').mkdir(parents=True)
    (raw / 'annotations').mkdir()
    for name, color in [('one.jpg', 'white'), ('unknown.jpg', 'black')]:
        Image.new('RGB', (100,50), color).save(raw / 'images' / name)
    xml_file(raw / 'annotations', positive=('Background',))
    with pytest.raises(ValueError, match='lack XML'):
        prepare(raw, tmp_path / 'out')
    result = prepare(raw, tmp_path / 'out', exclude_unannotated=True)
    assert result['excluded_missing_xml'] == ['unknown.jpg']
    assert list(result['images']) == ['one.jpg']
    assert (tmp_path / 'out/labels/test/one.txt').read_text() == ''
    assert json.loads((tmp_path / 'annotation_audit.json').read_text())['missing_xml_semantics'] == 'unknown, NOT negative'
    with pytest.raises(FileExistsError):
        prepare(raw, tmp_path / 'out', exclude_unannotated=True)
