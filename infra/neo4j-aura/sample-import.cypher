MERGE (a:Intersection {node_id: "demo_i_001"})
SET a.lat = 21.0278, a.lon = 105.8342
MERGE (b:Intersection {node_id: "demo_i_002"})
SET b.lat = 21.0320, b.lon = 105.8401
MERGE (s1:RoadSegment {segment_id: "HN_DEMO_001"})
SET s1.city = "hanoi",
    s1.district = "ba_dinh",
    s1.road_class = "primary",
    s1.length_m = 720.0,
    s1.current_jam_factor = 7.2,
    s1.risk_score = 68.5
MERGE (s2:RoadSegment {segment_id: "HN_DEMO_002"})
SET s2.city = "hanoi",
    s2.district = "ba_dinh",
    s2.road_class = "secondary",
    s2.length_m = 510.0,
    s2.current_jam_factor = 5.8,
    s2.risk_score = 54.0
MERGE (s1)-[:STARTS_AT]->(a)
MERGE (s1)-[:ENDS_AT]->(b)
MERGE (s2)-[:UPSTREAM_OF {distance_m: 500.0, direction: "inbound"}]->(s1);
