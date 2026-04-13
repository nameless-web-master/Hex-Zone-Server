import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
from app.schemas.schemas import ZoneResponse
from geoalchemy2.elements import WKTElement
from types import SimpleNamespace
z = SimpleNamespace(
    id=1,
    zone_id='z1',
    owner_id=3,
    zone_type='geofence',
    name='Test',
    description='desc',
    h3_cells=[],
    geo_fence_polygon=WKTElement(
        'MULTIPOLYGON(((-73.9682 40.8670,-74.0904 40.7423,-73.8858 40.7925,-73.9579 40.8527,-73.9675 40.8673,-73.9675 40.8662,-73.9688 40.8665,-73.9688 40.8665,-73.9685 40.8673,-73.9685 40.8673,-73.9682 40.8670))))',
        srid=4326,
    ),
    parameters={},
    active=True,
    created_at='2026-04-13T00:00:00',
    updated_at='2026-04-13T00:00:00',
)
try:
    print(ZoneResponse.model_validate(z).model_dump())
except Exception as e:
    import traceback
    traceback.print_exc()
