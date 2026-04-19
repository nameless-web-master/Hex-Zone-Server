import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
from app.crud.zone import _geojson_to_geometry
geojson = {
    'type': 'MultiPolygon',
    'coordinates': [
        [
            [
                [
                    -73.964424133, 40.875621535
                ],
                [
                    -74.085273743, 40.79093771
                ],
                [
                    -73.906059265, 40.787558505
                ],
                [
                    -73.922538757, 40.852513065
                ],
                [
                    -73.964767456, 40.87432352
                ],
                [
                    -73.964424133, 40.875621535
                ]
            ]
        ]
    ]
}
expr = _geojson_to_geometry(geojson)
print(type(expr))
print(expr)
print(expr.compile())
