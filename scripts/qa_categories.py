"""QA loader + validator for hierarchical categories, inherited attributes,
duplicate validation and product creation. Non-destructive: uses a 'QA-' prefix.

Run: python3 scripts/qa_categories.py
"""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"
PREFIX = "QA-"
TOKEN = None
results = []  # (case, ok, detail)


def call(method, path, body=None, token=None, raw=False):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt and not raw else txt)
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, txt


def login():
    global TOKEN
    url = BASE + "/auth/login"
    data = b"username=admin&password=osiris123"
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as r:
        TOKEN = json.loads(r.read().decode())["access_token"]


# --- data: (name, parent, [ (attr, type, required, options) ]) ; type 'list' -> 'select'
DATA = [
    ("Tecnología", None, [
        ("Marca", "text", True, None),
        ("Modelo", "text", False, None),
        ("Número de serie", "text", False, None),
    ]),
    ("Oficina", None, [
        ("Marca", "text", False, None),
        ("Unidad de medida", "list", True, ["unidad", "caja", "paquete", "resma"]),
        ("Presentación", "text", False, None),
    ]),
    ("Mobiliario", None, [
        ("Material principal", "text", False, None),
        ("Color principal", "text", False, None),
        ("Uso recomendado", "list", False, ["oficina", "hogar", "industrial", "educativo"]),
    ]),
    ("Computadoras", "Tecnología", [
        ("Procesador", "text", True, None),
        ("Memoria RAM GB", "integer", True, None),
        ("Almacenamiento GB", "integer", True, None),
        ("Tipo de almacenamiento", "list", True, ["HDD", "SSD", "NVMe", "eMMC"]),
    ]),
    ("Laptops", "Computadoras", [
        ("Tamaño de pantalla pulgadas", "decimal", True, None),
        ("Tipo de batería", "text", False, None),
        ("Sistema operativo", "list", False, ["Windows", "Linux", "macOS", "ChromeOS", "Sin sistema operativo"]),
        ("Peso kg", "decimal", False, None),
    ]),
    ("Computadoras de escritorio", "Computadoras", [
        ("Tipo de gabinete", "list", False, ["Torre", "Mini torre", "Small Form Factor", "All in One"]),
        ("Fuente de poder watts", "integer", False, None),
        ("Incluye monitor", "boolean", True, None),
    ]),
    ("Servidores", "Computadoras", [
        ("Tipo de servidor", "list", True, ["Rack", "Torre", "Blade"]),
        ("Número de procesadores soportados", "integer", False, None),
        ("Soporte RAID", "boolean", False, None),
    ]),
    ("Periféricos", "Tecnología", [
        ("Tipo de conexión", "list", True, ["USB", "Bluetooth", "WiFi", "Cableado", "Inalámbrico"]),
        ("Compatibilidad", "text", False, None),
        ("Requiere batería", "boolean", True, None),
    ]),
    ("Teclados", "Periféricos", [
        ("Tipo de teclado", "list", True, ["Membrana", "Mecánico", "Ergonómico"]),
        ("Idioma de teclado", "list", True, ["Español", "Inglés"]),
        ("Retroiluminado", "boolean", True, None),
    ]),
    ("Mouse", "Periféricos", [
        ("DPI máximo", "integer", False, None),
        ("Tipo de sensor", "list", False, ["Óptico", "Láser"]),
        ("Número de botones", "integer", False, None),
    ]),
    ("Monitores", "Tecnología", [
        ("Tamaño de pantalla pulgadas", "decimal", True, None),
        ("Resolución de pantalla", "list", True, ["HD", "Full HD", "2K", "4K"]),
        ("Tasa de refresco Hz", "integer", False, None),
        ("Tipo de panel", "list", False, ["IPS", "VA", "TN", "OLED"]),
    ]),
    ("Impresoras", "Tecnología", [
        ("Tecnología de impresión", "list", True, ["Inyección de tinta", "Láser", "Térmica", "Matricial"]),
        ("Conectividad de impresión", "list", True, ["USB", "WiFi", "Ethernet", "Bluetooth"]),
        ("Multifunción", "boolean", True, None),
    ]),
    ("Papelería", "Oficina", [
        ("Tamaño de papel", "list", False, ["A4", "Carta", "Oficio", "A3"]),
        ("Gramaje gsm", "integer", False, None),
        ("Reciclado", "boolean", False, None),
    ]),
    ("Cuadernos", "Papelería", [
        ("Número de hojas", "integer", True, None),
        ("Tipo de rayado", "list", True, ["Cuadros", "Líneas", "Blanco", "Mixto"]),
        ("Encuadernación", "list", False, ["Espiral", "Grapado", "Cosido", "Pegado"]),
    ]),
    ("Carpetas", "Papelería", [
        ("Material de carpeta", "list", False, ["Cartón", "Plástico", "Vinil"]),
        ("Tipo de cierre", "list", False, ["Elástico", "Broche", "Anillas", "Sin cierre"]),
        ("Capacidad de hojas", "integer", False, None),
    ]),
    ("Escritura", "Oficina", [
        ("Color de tinta", "list", True, ["Azul", "Negro", "Rojo", "Verde", "Multicolor"]),
        ("Tipo de punta escritura", "list", False, ["Fina", "Media", "Gruesa"]),
    ]),
    ("Esferos", "Escritura", [
        ("Tecnología de escritura", "list", False, ["Bola", "Roller", "Gel"]),
        ("Grosor mm", "decimal", False, None),
        ("Retráctil", "boolean", True, None),
    ]),
    ("Marcadores", "Escritura", [
        ("Tipo de marcador", "list", True, ["Permanente", "Pizarra", "Resaltador"]),
        ("Recargable", "boolean", False, None),
        ("Punta biselada", "boolean", False, None),
    ]),
    ("Sillas", "Mobiliario", [
        ("Tipo de silla", "list", True, ["Oficina", "Ejecutiva", "Visitante", "Ergonómica"]),
        ("Ajustable en altura", "boolean", True, None),
        ("Soporte lumbar", "boolean", False, None),
        ("Capacidad máxima kg", "decimal", False, None),
    ]),
    ("Escritorios", "Mobiliario", [
        ("Largo cm", "decimal", True, None),
        ("Ancho cm", "decimal", True, None),
        ("Alto cm", "decimal", True, None),
        ("Número de cajones", "integer", False, None),
    ]),
]

ids = {}  # logical name -> category id
attr_summary = {}  # name -> list of created attr names


def create_categories():
    created = 0
    for name, parent, _ in DATA:
        pid = ids.get(parent) if parent else None
        st, resp = call("POST", "/categories", {"name": PREFIX + name, "parent_id": pid}, TOKEN)
        if st == 201:
            ids[name] = resp["id"]
            created += 1
        else:
            results.append((f"crear categoría {name}", False, f"{st} {resp}"))
    return created


def create_attributes():
    total = 0
    for name, _, attrs in DATA:
        cid = ids[name]
        created_here = []
        for an, atype, req, opts in attrs:
            dt = "select" if atype == "list" else atype
            body = {"name": an, "data_type": dt, "is_required": req}
            if dt == "select":
                body["select_options"] = opts
            st, resp = call("POST", f"/categories/{cid}/attributes", body, TOKEN)
            if st == 201:
                total += 1
                created_here.append(an)
            else:
                results.append((f"atributo {an} en {name}", False, f"{st} {resp.get('code') if isinstance(resp,dict) else resp}"))
        attr_summary[name] = created_here
    return total


def inherited_names(cat_name):
    cid = ids[cat_name]
    st, resp = call("GET", f"/categories/{cid}/attributes", token=TOKEN)
    return [a["name"] for a in resp] if st == 200 else []


def expect(case, cond, detail=""):
    results.append((case, bool(cond), detail))


def run():
    login()
    n_cat = create_categories()
    expect("Carga: 20 categorías creadas", n_cat == 20, f"{n_cat}/20")
    n_attr = create_attributes()
    expect("Carga: atributos creados", n_attr > 0, f"{n_attr} atributos")

    # --- Inheritance counts ---
    checks = [("Laptops", 11), ("Mouse", 9), ("Cuadernos", 9), ("Esferos", 8), ("Sillas", 7)]
    for cat, exp in checks:
        names = inherited_names(cat)
        # dedup case-insensitive to confirm no duplicates shown
        norm = [x.strip().lower() for x in names]
        no_dups = len(norm) == len(set(norm))
        expect(f"Herencia {cat}: {exp} atributos, sin duplicados",
               len(names) == exp and no_dups, f"obtuvo {len(names)} {'(con dup!)' if not no_dups else ''}")

    # CASE 5/6: duplicate in child (ancestor has it)
    st, r = call("POST", f"/categories/{ids['Laptops']}/attributes", {"name": "Marca", "data_type": "text"}, TOKEN)
    expect("Caso 5: 'Marca' en Laptops bloqueado (heredado de Tecnología)",
           st == 409 and r.get("code") == "DUPLICATE_ATTRIBUTE_IN_HIERARCHY", f"{st} {r.get('code')}")
    st, r = call("POST", f"/categories/{ids['Computadoras']}/attributes", {"name": "marca", "data_type": "text"}, TOKEN)
    expect("Caso 6: 'marca' (minúsculas) en Computadoras bloqueado",
           st == 409 and r.get("code") == "DUPLICATE_ATTRIBUTE_IN_HIERARCHY", f"{st} {r.get('code')}")
    # CASE 7: spaces
    st, r = call("POST", f"/categories/{ids['Periféricos']}/attributes", {"name": "  Marca  ", "data_type": "text"}, TOKEN)
    expect("Caso 7: '  Marca  ' (espacios) en Periféricos bloqueado",
           st == 409 and r.get("code") == "DUPLICATE_ATTRIBUTE_IN_HIERARCHY", f"{st} {r.get('code')}")
    # CASE 8: same name in different roots allowed -> already created Marca in Tecnología, Oficina, Mobiliario
    has_oficina_marca = "Marca" in attr_summary.get("Oficina", [])
    has_mob_marca = False  # Mobiliario has no 'Marca' by design
    expect("Caso 8: 'Marca' coexiste en ramas distintas (Tecnología y Oficina)",
           "Marca" in attr_summary.get("Tecnología", []) and has_oficina_marca, f"oficina={has_oficina_marca}")
    # CASE 10: create attr in parent that exists in a descendant
    st, r = call("POST", f"/categories/{ids['Tecnología']}/attributes", {"name": "DPI máximo", "data_type": "integer"}, TOKEN)
    expect("Caso 10: 'DPI máximo' en Tecnología bloqueado (existe en hija Mouse)",
           st == 409 and r.get("code") == "DUPLICATE_ATTRIBUTE_IN_DESCENDANTS", f"{st} {r.get('code')}")

    # CASE 9: move Oficina under Tecnología (both have 'Marca') -> blocked
    st, r = call("PATCH", f"/categories/{ids['Oficina']}", {"parent_id": ids["Tecnología"]}, TOKEN)
    expect("Caso 9: mover Oficina bajo Tecnología bloqueado (Marca duplicada)",
           st == 409 and r.get("code") == "CATEGORY_MOVE_DUPLICATE_ATTRIBUTES", f"{st} {r.get('code')} {r.get('message','')[:60]}")

    # --- Products ---
    def make_product(name, cat, attrs, pvp="10.00", stock_min="1"):
        body = {"name": PREFIX + name, "category_id": ids[cat], "pvp": pvp,
                "stock_minimo": stock_min, "custom_attributes": attrs}
        return call("POST", "/products", body, TOKEN)

    # CASE 3: Laptop with 11 attrs
    st, r = make_product("Laptop Dell Latitude 5440", "Laptops", {
        "Marca": "Dell", "Modelo": "Latitude 5440", "Número de serie": "DL-TEST-001",
        "Procesador": "Intel Core i7", "Memoria RAM GB": 16, "Almacenamiento GB": 512,
        "Tipo de almacenamiento": "SSD", "Tamaño de pantalla pulgadas": 14,
        "Tipo de batería": "Litio", "Sistema operativo": "Windows", "Peso kg": 1.45,
    }, pvp="1150.00", stock_min="2")
    laptop_id = r.get("id") if st == 201 else None
    expect("Caso 3: crear Laptop con 11 atributos", st == 201, f"{st} {r.get('code') if isinstance(r,dict) else r}")

    # CASE 4: Mouse 9 attrs
    st, r = make_product("Mouse Logitech M185", "Mouse", {
        "Marca": "Logitech", "Modelo": "M185", "Número de serie": "LOG-M185-001",
        "Tipo de conexión": "Inalámbrico", "Compatibilidad": "Windows/Linux/macOS",
        "Requiere batería": True, "DPI máximo": 1000, "Tipo de sensor": "Óptico",
        "Número de botones": 3,
    }, pvp="18.00", stock_min="10")
    expect("Caso 4: crear Mouse con 9 atributos", st == 201, f"{st} {r.get('code') if isinstance(r,dict) else r}")

    # CASE 11: Monitor with list values
    st, r = make_product("Monitor LG UltraGear 27", "Monitores", {
        "Marca": "LG", "Modelo": "UltraGear 27", "Número de serie": "LG-MON-001",
        "Tamaño de pantalla pulgadas": 27, "Resolución de pantalla": "4K",
        "Tasa de refresco Hz": 144, "Tipo de panel": "IPS",
    })
    expect("Caso 11: crear Monitor (valores list válidos)", st == 201, f"{st} {r.get('code') if isinstance(r,dict) else r}")
    # invalid list value
    st2, r2 = make_product("Monitor Bad List", "Monitores", {
        "Marca": "X", "Tamaño de pantalla pulgadas": 24, "Resolución de pantalla": "8K",
    })
    expect("Caso 11b: valor fuera de lista rechazado", st2 == 422, f"{st2} {r2.get('code') if isinstance(r2,dict) else r2}")

    # CASE 14: Teclado booleans
    st, r = make_product("Teclado Redragon Kumara", "Teclados", {
        "Marca": "Redragon", "Modelo": "Kumara", "Número de serie": "RD-KUM-001",
        "Tipo de conexión": "USB", "Compatibilidad": "Windows/Linux",
        "Requiere batería": False, "Tipo de teclado": "Mecánico",
        "Idioma de teclado": "Español", "Retroiluminado": True,
    })
    expect("Caso 14: crear Teclado (booleanos)", st == 201, f"{st} {r.get('code') if isinstance(r,dict) else r}")

    # CASE 12: required missing
    st, r = make_product("Laptop Sin Requeridos", "Laptops", {"Modelo": "x"})
    expect("Caso 12: Laptop sin requeridos rechazada", st == 422 and r.get("code") == "MISSING_REQUIRED_ATTRIBUTE", f"{st} {r.get('code')}")

    # CASE 13: invalid types
    st, r = make_product("Laptop Tipos Malos", "Laptops", {
        "Marca": "X", "Procesador": "i5", "Memoria RAM GB": "dieciséis",
        "Almacenamiento GB": 256, "Tipo de almacenamiento": "SSD",
        "Tamaño de pantalla pulgadas": 14,
    })
    expect("Caso 13: tipo inválido (RAM='dieciséis') rechazado", st == 422 and r.get("code") == "INVALID_ATTRIBUTE_VALUE", f"{st} {r.get('code')}")

    # CASE 16: change attr type with existing values -> blocked
    # find Procesador attr id in Computadoras
    st, attrs = call("GET", f"/categories/{ids['Computadoras']}/attributes", token=TOKEN)
    ram = next((a for a in attrs if a["name"] == "Memoria RAM GB"), None)
    if ram:
        st, r = call("PATCH", f"/categories/{ids['Computadoras']}/attributes/{ram['id']}",
                     {"data_type": "text"}, TOKEN)
        expect("Caso 16: cambiar tipo de 'Memoria RAM GB' (con datos) bloqueado",
               st == 409 and r.get("code") == "ATTRIBUTE_TYPE_CHANGE_BLOCKED", f"{st} {r.get('code')}")

    # CASE 17: delete attr used by products -> blocked
    proc = next((a for a in attrs if a["name"] == "Procesador"), None)
    if proc:
        st, r = call("DELETE", f"/categories/{ids['Computadoras']}/attributes/{proc['id']}", token=TOKEN)
        expect("Caso 17: eliminar 'Procesador' (usado por productos) bloqueado",
               st == 409 and r.get("code") == "ATTRIBUTE_IN_USE", f"{st} {r.get('code')}")

    # --- print report ---
    print("\n================ RESULTADOS QA ================")
    ok = sum(1 for _, p, _ in results if p)
    for case, passed, detail in results:
        print(f"[{'PASS' if passed else 'FAIL'}] {case}" + (f"  -> {detail}" if detail else ""))
    print(f"\nTOTAL: {ok}/{len(results)} OK")
    print("\nCategorías:", ", ".join(f"{k}={v}" for k, v in ids.items()))


if __name__ == "__main__":
    run()
