import json
with open(r'C:\Users\DELL\Desktop\search1.json') as f:
    data = json.load(f)
print(f"Total: {data.get('total_count',0)}")
for r in data.get('items',[]):
    desc = r['description'][:80] if r['description'] else 'None'
    print(f"  {r['full_name']:55s} {desc}")
print("---")
with open(r'C:\Users\DELL\Desktop\search2.json') as f:
    data = json.load(f)
print(f"Total: {data.get('total_count',0)}")
for r in data.get('items',[]):
    desc = r['description'][:80] if r['description'] else 'None'
    print(f"  {r['full_name']:55s} {desc}")
