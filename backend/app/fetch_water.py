import json
import requests

# Paradise coordinates (South, West, North, East)
BBOX = "39.715,-121.650,39.790,-121.570"

query = f"""
[out:json][timeout:30];
(
  node["emergency"="fire_hydrant"]({BBOX});
  node["amenity"="fire_hydrant"]({BBOX});
  node["water"]({BBOX});
  node["natural"="water"]({BBOX});
  node["waterway"]({BBOX});
  way["natural"="water"]({BBOX});
  way["waterway"]({BBOX});
);
out body center;
>;
out skel qt;
"""

headers = {
    "User-Agent": "CityShield_Wildfire_Data_Fetcher/1.0 (Datathon Project)",
    "Accept": "application/json"
}

endpoints = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

def fetch_water():
    print("Fetching OpenStreetMap Paradise hydrants info...")
    
    resp = None
    for url in endpoints:
        try:
            print(f"connecting: {url}")
            r = requests.post(url, data={"data": query}, headers=headers, timeout=20)
            if r.status_code == 200:
                elements = r.json().get("elements", [])
                if len(elements) > 0:
                    resp = r
                    print(f"successfully get original data from {url} ")
                    break
                else:
                    print(f"Node {url} return 0, trying the other node...")
            else:
                print(f"Returned {r.status_code}, finding the next node...")
        except Exception as e:
            print(f"Time out: {e}")

    if resp and resp.status_code == 200:
        elements = resp.json().get("elements", [])
        water_list = []
        
        for elem in elements:
            tags = elem.get("tags", {})
            
        
            lat = elem.get("lat") or elem.get("center", {}).get("lat")
            lon = elem.get("lon") or elem.get("center", {}).get("lon")
            
            if not lat or not lon:
                continue
                
            w_type = tags.get("emergency") or tags.get("natural") or tags.get("waterway") or "water_source"
            w_name = tags.get("name") or f"Water Point ({w_type})"
            
            water_list.append({
                "id": f"osm_{elem['id']}",
                "type": w_type,
                "name": w_name,
                "lat": lat,
                "lon": lon,
                "status": "active"
            })
                
        print(f"Finished. {len(water_list)} hydrants/water position.")
        
        with open("water_sources.json", "w", encoding="utf-8") as f:
            json.dump(water_list, f, indent=2, ensure_ascii=False)
        print("Generated water_sources.json！")
    else:
        print("No effective data.")

if __name__ == "__main__":
    fetch_water()