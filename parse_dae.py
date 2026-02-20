import xml.etree.ElementTree as ET
try:
    tree = ET.parse('nanobot/daemon/static/models/digivice/ID00021_00000000.dae')
    root = tree.getroot()
    ns = {'ns': root.tag.split('}')[0].strip('{')}
    materials = root.findall('.//ns:library_materials/ns:material', ns)
    print("Materials:", [(m.attrib.get('id', ''), m.attrib.get('name', '')) for m in materials])
except Exception as e:
    print(e)
