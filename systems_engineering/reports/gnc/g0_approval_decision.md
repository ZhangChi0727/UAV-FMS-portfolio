# GNC G0: namespace migration

On 2026-11-27 the Owner authorized new contract and requirement identities, without
an import alias or a history rewrite. This decision is about naming, not new model
parameters, a new numerical acceptance decision, or closed-loop performance.
The current development contract is [gnc-g0-contract/v2](../../../gnc_baseline/integration/configs/gnc_g0_contract.v2.json).
Its predecessor's October approval applies to the predecessor bytes only.
The synthetic envelope and the two CTL non-applicability decisions are unchanged.

Historical objects retained in parent revision `15651ebfc87da6b671c17618f5d9aaf50f660322`:

| Object | Git blob |
| --- | --- |
| Original approval record (including its original authors and dates) | `293fe48e6ba23f7cd7bacb65b2f4d9d418b037c3` |
| Predecessor G0 v2, canonical LF | `1beff6e6a9a81d0ab92b2059a93207ffed9d291d` |

For a byte-level check in Bash, `git cat-file blob 1beff6e6a9a81d0ab92b2059a93207ffed9d291d | sha256sum`
must yield `5b95531a6f96cb67ce25f624d6921bd313696f3c0b9868ec1de13c24c34cd98c`.
Current component designs pin their **own** G0 digest in their authority blocks.
