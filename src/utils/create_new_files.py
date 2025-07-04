from datetime import timedelta

# Define the script segments with timestamps for .srt format
script_segments = [
    ("Hook", "Every year, ships run aground in harbors worldwide—not because of human error, but because the seafloor changed... and nobody knew. What if we could scan the seafloor as easily as we scan barcodes?", 15),
    ("Introduction", "In today's video, we explore how LiDAR—originally used for terrain mapping—is now transforming marine navigation. With rising sea levels and shifting coastlines, accurate and real-time depth data is no longer optional. It's critical.", 30),
    ("What is LiDAR?", "LiDAR stands for Light Detection and Ranging. It works by firing rapid laser pulses toward a surface and measuring the time it takes for the reflection to return. This gives us incredibly accurate elevation data.", 25),
    ("Bathymetric Application", "In marine environments, a specialized form called bathymetric LiDAR is used. Unlike standard LiDAR, it uses green wavelengths, which penetrate water. Mounted on aircraft, it scans coastal and shallow water zones, detecting underwater features like sandbars, shoals, and submerged debris.", 35),
    ("Importance for Navigation", "Traditional nautical charts can be outdated or incomplete. With LiDAR, ports and naval authorities get high-resolution updates—quickly. This means safer passages for vessels, especially in places where sediment shifts rapidly after storms or dredging.", 30),
    ("Real-world Example", "One U.S. Army Corps of Engineers project used LiDAR to map the Mississippi River's delta after Hurricane Ida. Within 48 hours, teams had new channel data that would've taken weeks with boats and sonar. The result? Faster reopening of a major shipping lane.", 30),
    ("Professional Insight", "Having worked on coastal infrastructure projects myself, I've seen firsthand how relying on outdated bathymetric data can delay operations and even damage equipment. Integrating LiDAR with GIS gives teams a clearer, safer picture—literally.", 20),
    ("Conclusion", "As global trade grows and coastlines shift, LiDAR is becoming a cornerstone of marine navigation. It's fast, accurate, and safer than traditional methods. If you found this video helpful, consider subscribing for more geospatial insights—faceless, but full of substance.", 25)
]

# Generate .srt content
srt_lines = []
start_time = timedelta(seconds=0)

for idx, (title, text, duration) in enumerate(script_segments, start=1):
    end_time = start_time + timedelta(seconds=duration)
    srt_lines.append(f"{idx}")
    srt_lines.append(f"{str(start_time)[:-3].zfill(8).replace('.', ',')} --> {str(end_time)[:-3].zfill(8).replace('.', ',')}")
    srt_lines.append(text)
    srt_lines.append("")
    start_time = end_time

srt_content = "\n".join(srt_lines)

# Generate Markdown content
md_lines = ["# Enhancing Marine Navigation with LiDAR", ""]
for title, text, _ in script_segments:
    md_lines.append(f"## {title}")
    md_lines.append(text)
    md_lines.append("")

md_content = "\n".join(md_lines)

# Save both files
from pathlib import Path

md_path = Path(Path().absolute(), "enhancing_marine_navigation_lidar.md")
srt_path = Path(Path().absolute(), "enhancing_marine_navigation_lidar.srt")

md_path.write_text(md_content)
srt_path.write_text(srt_content)

