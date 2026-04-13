import os

filepath = r"c:\Users\Admin\Documents\vscode\LangChain_backend\app\routers\products.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

parts = content.split("# ==================== PRODUCTION LIST ====================")
if len(parts) > 1:
    before_prod = parts[0]
    prod_block = "# ==================== PRODUCTION LIST ====================" + parts[1]
    
    get_product_str = '@router.get("/{product_id}", response_model=ProductOut)'
    subparts = before_prod.split(get_product_str)
    
    new_content = subparts[0] + prod_block + "\n\n" + get_product_str + subparts[1]
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Fixed!")
else:
    print("Already fixed?")
