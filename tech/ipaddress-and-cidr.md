# ipaddress and CIDR ranges

## 1. What it is

An **IP address** is the number that identifies a machine on a network, written as four numbers from 0 to 255, such as `10.50.0.7`. A **CIDR range** (read "sider") names a whole block of addresses in one short text: `10.50.0.0/24`. The number after the slash says how many of the 32 bits at the start are fixed. `/24` fixes the first 24 bits (`10.50.0`), which leaves 8 bits free: 2⁸ = 256 addresses, from `10.50.0.0` to `10.50.0.255`. A smaller number after the slash means a bigger block: `/16` is 65,536 addresses. `ipaddress` is the Python standard-library module that understands these texts.

## 2. Why this repository uses it

The shared network has two subnets, and two subnets that share an address would hand the same address to two machines. The tool must catch an overlap in the design file before anyone builds the network. The module also rejects text that is not a range at all.

## 3. Where it appears

| Path | What it does |
| --- | --- |
| `design/landing-zone.yaml` | Holds the ranges as text: the two subnets `10.50.0.0/24` and `10.60.0.0/24`, and the `office` access level `203.0.113.0/24`. |
| `src/landing_zone/infrastructure/yaml_files.py` | Turns each text into an `IPv4Network` object while loading. |
| `src/landing_zone/domain/design.py` | Stores the objects and finds overlaps (`_overlaps`). |
| `infra/modules/shared-vpc/main.tf` | Gives each range to a real subnet (`ip_cidr_range`). |
| `tests/unit/domain/test_design.py` | Builds an overlapping range and expects the problem to be reported. |

## 4. How it works underneath

An IPv4 address is one 32-bit number; the dotted form is only a way to write it. A range is an address plus a **prefix length**. The first address of the range is the **network address**; the **netmask** (`255.255.255.0` for `/24`) is the 32-bit number with the fixed bits set to 1. An address is inside the range when it equals the network address in all the fixed bits. Two ranges **overlap** when one contains an address of the other. Because ranges are aligned blocks, two ranges either do not touch at all or one contains the other.

Writing `10.50.0.1/24` is a mistake in a range: the last bits should be zero. `ipaddress.IPv4Network` is strict by default and raises `ValueError` ("has host bits set"), which stops a typo that would silently mean something else.

A Google Cloud subnet keeps four addresses of its primary range for itself (the first two and the last two), so a `/24` gives a team 252 usable addresses, not 256. `10.0.0.0/8`, `172.16.0.0/12` and `192.168.0.0/16` are **private** ranges for use inside organizations. `203.0.113.0/24` is reserved for documentation, so it matches no real machine, which is why the design file uses it as a placeholder for "your office".

## 5. Walkthrough of this repository's use

`src/landing_zone/infrastructure/yaml_files.py`

```python
            subnets=tuple(
                Subnet(
                    str(s["name"]),
                    ipaddress.IPv4Network(s["cidr"]),
                    str(s["service_project"]),
                    tuple(str(g) for g in s.get("user_groups", [])),
                )
                for s in vpc["subnets"]
            ),
```

`ipaddress.IPv4Network(s["cidr"])` converts the text into an object. A bad text raises `ValueError`; the surrounding `try` turns that into `InvalidDesign` with the file name, so the user sees a clear error and not a traceback.

`src/landing_zone/domain/design.py`

```python
def _overlaps(subnets: tuple[Subnet, ...]) -> list[str]:
    out = []
    for index, first in enumerate(subnets):
        for second in subnets[index + 1 :]:
            if first.cidr.overlaps(second.cidr):
                out.append(f"subnets {first.name} ({first.cidr}) and {second.name} ({second.cidr}) overlap")
    return out
```

- `enumerate(subnets)` gives each item with its position.
- `subnets[index + 1 :]` is "every subnet after this one", so each pair is compared once and no subnet is compared with itself.
- `first.cidr.overlaps(second.cidr)` is the whole check. The message shows both names and both ranges so the reader knows what to change.

The test builds a deliberate clash:

`tests/unit/domain/test_design.py`

```python
def test_overlapping_subnets_are_reported(without, design):
    first, second = design.subnets
    clash = replace(second, cidr=ipaddress.ip_network("10.50.0.128/25"))
    problems = validate_design(without(subnets=(first, clash)))
    assert any("overlap" in p for p in problems)
```

`10.50.0.128/25` lies inside `10.50.0.0/24`, so the two overlap. The test replaces one subnet's range with it and expects a problem containing the word "overlap".

## 6. Try it yourself

```bash
.venv/bin/python -c "
import ipaddress as i
a = i.IPv4Network('10.50.0.0/24')
print(a.num_addresses, a.network_address, a.netmask)"
```
Expected: `256 10.50.0.0 255.255.255.0`

```bash
.venv/bin/python -c "
import ipaddress as i
a = i.IPv4Network('10.50.0.0/24')
print(a.overlaps(i.IPv4Network('10.60.0.0/24')), i.IPv4Network('10.50.0.0/16').overlaps(a))"
```
Expected: `False True` (the first pair is disjoint; the `/16` contains the `/24`).

```bash
.venv/bin/python -c "
import ipaddress as i
print(i.IPv4Address('10.50.0.7') in i.IPv4Network('10.50.0.0/24'), i.IPv4Address('10.60.0.7') in i.IPv4Network('10.50.0.0/24'))"
```
Expected: `True False`

```bash
.venv/bin/python -c "
import ipaddress as i
try:
    i.IPv4Network('10.50.0.1/24')
except ValueError as error:
    print(error)"
```
Expected: `10.50.0.1/24 has host bits set`

```bash
.venv/bin/python -m pytest tests/unit/domain/test_design.py -q -p no:cacheprovider -k overlapping
```
Expected: `1 passed, 8 deselected`.

## 7. Mistakes people make

- **Counting `/24` as 254 or 256 usable addresses.** Google Cloud reserves four, so 252 are usable.
- **Overlapping ranges in a shared network.** Two subnets with the same addresses cannot both be created; the design check finds it before the cloud does.
- **Host bits in a range** (`10.50.0.1/24`). Strict parsing rejects it.
- **Comparing ranges as text.** `"10.50.0.0/24" != "10.50.0.0/25"` tells you nothing about overlap; parse them.
- **Using a public range as a placeholder.** Use a documentation range (`203.0.113.0/24`, `198.51.100.0/24`, `192.0.2.0/24`) so the example cannot match a real machine.

## 8. Check yourself

1. How many addresses does a `/24` hold? *256 (2⁸).*
2. Is `/16` a bigger or a smaller block than `/24`? *Bigger: fewer fixed bits.*
3. What does `overlaps` return for `10.50.0.0/16` and `10.50.0.0/24`? *`True`: the first contains the second.*
4. Why does `IPv4Network('10.50.0.1/24')` fail? *The text has host bits set; strict parsing refuses it.*
5. Why does the design file use `203.0.113.0/24` for the office? *It is a documentation range that matches no real machine.*

## 9. Further reading

- `ipaddress` module: <https://docs.python.org/3.12/library/ipaddress.html>
- Subnet ranges in a VPC network (reserved addresses): <https://cloud.google.com/vpc/docs/subnets>
- RFC 5737, documentation address blocks: <https://www.rfc-editor.org/rfc/rfc5737>
