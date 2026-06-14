CREATE CONSTRAINT road_node_id IF NOT EXISTS
FOR (n:RoadNode)
REQUIRE n.node_id IS UNIQUE;

CREATE CONSTRAINT road_segment_id IF NOT EXISTS
FOR (s:RoadSegment)
REQUIRE s.segment_id IS UNIQUE;

CREATE CONSTRAINT intersection_id IF NOT EXISTS
FOR (i:Intersection)
REQUIRE i.node_id IS UNIQUE;

CREATE CONSTRAINT district_key IF NOT EXISTS
FOR (d:District)
REQUIRE (d.city, d.name) IS UNIQUE;
