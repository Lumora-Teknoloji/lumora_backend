import sys
import os
import asyncio
import json
import logging
from sqlalchemy.future import select

# PATH AYARI (app modülünü bulabilmesi için)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import async_session
from app.models.product import Product
from app.services.core.clients import openai_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BATCH_SIZE = 50

async def auto_categorize():
    if not openai_client:
        logger.error("OpenAI Client is missing. Please check OPENAI_API_KEY in .env")
        return

    async with async_session() as session:
        # Boş kategorili ürünleri bul
        query = select(Product).filter((Product.category == None) | (Product.category == ''))
        result = await session.execute(query)
        products = result.scalars().all()
        
        if not products:
            logger.info("🎉 Hiç kategorisiz ürün bulunamadı!")
            return
            
        logger.info(f"🚨 Kategorize edilecek ürün sayısı: {len(products)}")
        
        for i in range(0, len(products), BATCH_SIZE):
            batch = products[i:i+BATCH_SIZE]
            logger.info(f"İşleniyor: {i} - {i+len(batch)} / {len(products)}")
            
            prompt_data = []
            for p in batch:
                prompt_data.append({
                    "id": p.id,
                    "name": p.name or "Bilinmeyen Ürün",
                    "brand": p.brand or "Bilinmeyen Marka",
                    "url": p.url or ""
                })
            
            system_prompt = """Sen bir E-Ticaret ve Moda Uzmanısın. Botumuz Trendyol'dan veri çekerken bazı ürünlerin kategorisini anlayamadı.
GÖREVİN: Sana verilen ürün listesindeki ID, isim, URL ve markalara bakarak en mantıklı Trendyol kategori hiyerarşisini bulmak.
DİKKAT: Çıktın SADECE geçerli bir JSON objesi olmalıdır!

Örnek Çıktı Formatı:
{
  "1025": "Kadın > Kadın Giyim > Elbise",
  "1026": "Erkek > Erkek Giyim > T-Shirt",
  "1027": "Ev & Yaşam > Kırtasiye > Defter",
  "1028": "Genel Moda"
}

Asla markdown (```json) kullanma, direkt { ile başla } ile bitir."""
            
            try:
                # GPT-4o-mini kullanımı (Hızlı ve ucuz)
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(prompt_data, ensure_ascii=False)}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                updates = json.loads(content)
                
                updated_count = 0
                for p in batch:
                    cat = updates.get(str(p.id))
                    if cat:
                        p.category = cat
                        updated_count += 1
                
                await session.commit()
                logger.info(f"✅ Batch {i}-{i+len(batch)} tamamlandı. {updated_count} ürün veritabanında güncellendi.")
                
            except Exception as e:
                logger.error(f"❌ Batch {i} güncellenirken hata oluştu: {e}")
                await session.rollback()

if __name__ == "__main__":
    asyncio.run(auto_categorize())
