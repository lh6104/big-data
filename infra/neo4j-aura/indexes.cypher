CREATE INDEX road_segment_city IF NOT EXISTS
FOR (s:RoadSegment)
ON (s.city);

CREATE INDEX road_segment_district IF NOT EXISTS
FOR (s:RoadSegment)
ON (s.district);

CREATE INDEX road_segment_risk IF NOT EXISTS
FOR (s:RoadSegment)
ON (s.risk_score);

CREATE INDEX road_segment_jam IF NOT EXISTS
FOR (s:RoadSegment)
ON (s.current_jam_factor);

CREATE INDEX intersection_location IF NOT EXISTS
FOR (i:Intersection)
ON (i.lat, i.lon);
