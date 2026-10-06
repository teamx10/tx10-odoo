import ast, os, sys, json
ROOT="/Users/temich/dev/tx10/tx10-odoo"
paths=[f"{ROOT}/solar-demo/oca/{r}" for r in ["field-service","maintenance","rma","sign","geospatial"]]+[f"{ROOT}/addons",f"{ROOT}/odoo/addons"]
def find(m):
    for p in paths:
        f=os.path.join(p,m,"__manifest__.py")
        if os.path.exists(f): return p,ast.literal_eval(open(f).read())
    return None,None
targets=sys.argv[1].split(",")
seen={};order=[]
def walk(m,chain):
    if m in seen: return
    p,man=find(m)
    seen[m]=(p,man)
    if man is None: print("MISSING",m,"via"," > ".join(chain)); return
    for d in man.get("depends",[]): walk(d,chain+[m])
    order.append(m)
for t in targets: walk(t,[])
oca=[m for m in order if seen[m][0] and "/oca/" in seen[m][0]]
print("%-40s %-6s %-8s %-10s %-14s %s"%("module","repo","ver","inst","status","license / ext_deps"))
for m in oca:
    p,man=seen[m]
    print("%-40s %-6s %-8s %-10s %-14s %s %s"%(m,p.split('/')[-1][:6],man.get("version"),man.get("installable",True),man.get("development_status","-"),man.get("license"),man.get("external_dependencies",{})))
core=[m for m in order if seen[m][0] and "/oca/" not in seen[m][0]]
print("\nCORE deps (%d):"%len(core)," ".join(core))
ent=[m for m in order if seen[m][1] and seen[m][1].get("license","").startswith("OEEL")]
print("ENTERPRISE-licensed:",ent)
for m in core:
    e=seen[m][1].get("external_dependencies")
    if e: print("core ext", m, e)
