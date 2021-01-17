# sqfl

A query language that compiles to SQL(ite).

## Warnings

- Operator precedence is still WIP
- Not tested much against SQL injection

## Usage

```python
import sqfl

parser = sqfl.SqliteFilterParser()
ast = parser.parse("""
(
    (a.date > '2021-01-01')
    and (a.name = '123\\'test\\\\ing ( ) ) and or exists')
    and (a.seq <= 100)
)
or exists b (
    (b.name = 'Authorization')
    and (b.value != 'Basic')
    or exists c (c.value != 'Basic')
)
or exists b.d.e (
    (d.name = 'Authorization')
    and (e.value != 'Basic')
)
or (a.seq > 100)
""")

schema = {
    "a": {
        "columns": [
            "id",
            "name",
            "value",
            "date",
            "seq"
        ],
        "parents": [],
        "children": [
            "b"
        ]
    },
    "b": {
        "columns": [
            "id",
            "a_id",
            "name",
            "value"
        ],
        "parents": [
            "a"
        ],
        "children": [
            "c",
            "d"
        ]
    },
    "c": {
        "columns": [
            "id",
            "b_id",
            "name",
            "value"
        ],
        "parents": [
            "b"
        ],
        "children": [
            "e"
        ]
    },
    "d": {
        "columns": [
            "id",
            "b_id",
            "name",
            "value"
        ],
        "parents": [
            "b"
        ],
        "children": [
            "e"
        ]
    },
    "e": {
        "columns": [
            "id",
            "name",
            "value"
        ],
        "parents": [
            "c",
            "d"
        ],
        "children": []
    }
}

compiler = sqfl.SqliteFilterCompiler(schema)
print(compiler.compile(['a'], 1, ast))
```

## License

- Library: MIT
- Simple Parser: LGPL
