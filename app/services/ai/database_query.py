import logging
import json
from typing import Dict, Any, List
from sqlalchemy import text
from app.core.database import engine
from app.services.core.clients import openai_client

logger = logging.getLogger(__name__)

async def handle_database_query(user_message: str) -> Dict[str, Any]:
    """
    Directly queries the database for raw data using an AI-generated SQL query
    and formats the result back to the user.
    """
    if not openai_client:
        return {"content": "Sistem hatası: OpenAI istemcisi eksik.", "image_urls": [], "process_log": []}
    
    schema_info = """
    Table name: products
    Columns:
    - id: integer
    - product_code: character varying
    - name: character varying 
    - brand: character varying 
    - url: character varying
    - image_url: character varying
    - category: character varying (Breadcrumb format, e.g. "Trendyol > Kadın > Giyim > Pantolon")
    - last_price: double precision
    - last_engagement_score: double precision (Algorithmic popularity score)
    - rating: numeric (Product rating, 0 to 5)
    - review_count: integer (Number of reviews/comments)
    - favorite_count: integer (Absolute number of likes/favorites)
    - cart_count: integer (Number of adds to cart)
    - view_count: integer (Total views)
    - qa_count: integer (Number of Q&As)
    - trend_score: double precision
    - dominant_color: character varying
    - fabric_type: character varying
    - fit_type: character varying
    - first_seen_at: timestamp
    """

    sql_generation_prompt = f"""
    You are an expert Data Analyst and PostgreSQL database administrator.
    Given the schema below, write a PostgreSQL query that answers the user's request.
    
    {schema_info}
    
    RULES:
    1. Read-only queries only (SELECT). NEVER perform INSERT, UPDATE, DELETE, DROP.
    2. Write ONLY the raw SQL query. No explanation, no markdown blocks. Do not wrap in ```sql ... ```.
    3. If the user asks for "most liked", "en çok beğenilen", or specific likes/favorites, ALWAYS include `favorite_count` in your SELECT statement and ORDER BY favorite_count DESC NULLS LAST.
    4. If the user asks for "trendy", order by trend_score DESC NULLS LAST. 
    5. If the user asks for "kadın pantolon", use category ILIKE '%Kadın%' AND category ILIKE '%Pantolon%'.
    6. Always use LIMIT 10 to prevent massive outputs unless asked otherwise.
    7. Return ONLY the raw SQL text.
    8. SECURITY GUARDRAIL: Do not generate queries for any tables other than 'products'. If the user asks for unrelated topics (e.g., cooking recipes, personal data, system tables, passwords), return EXACTLY the string `DENIED_GUARD_TRIGGER`. Do NOT try to write SQL for unrelated requests.
    """

    try:
        # Step 1: Generate SQL 
        response = openai_client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": sql_generation_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.0
        )
        sql_query = response.choices[0].message.content.strip()
        
        # Strip markdown if AI stubbornly adds it
        if sql_query.startswith("```sql"):
            sql_query = sql_query[7:]
        if sql_query.startswith("```"):
            sql_query = sql_query[3:]
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip()
        
        logger.info(f"🔍 Generated SQL Query: {sql_query}")
        
        # Step 2: Ensure it's a SELECT query
        if sql_query == "DENIED_GUARD_TRIGGER":
            return {
                "content": "Üzgünüm, güvenlik ve gizlilik politikalarımız gereği yalnızca vitrindeki giyim ürünleri hakkında bilgi paylaşımı yapabiliyorum. Özel sistem verilerine veya alakasız konulara yanıt veremem.",
                "image_urls": [],
                "process_log": ["AI Guardrail Triggered: Request denied by prompt."]
            }
            
        if not sql_query.lower().startswith("select"):
            return {
                "content": "Üzgünüm, güvenlik nedeniyle yalnızca SEÇME (SELECT) sorguları çalıştırabilirim.",
                "image_urls": [],
                "process_log": ["SQL query was not a SELECT."]
            }
        
        # Step 3: Execute SQL
        with engine.connect() as conn:
            result = conn.execute(text(sql_query))
            rows = result.fetchall()
            keys = result.keys()
            data = [dict(zip(keys, row)) for row in rows]
            
        logger.info(f"📊 Query returned {len(data)} rows.")
        
        if not data:
            return {
                "content": "Bu sorguya uygun veritabanımızda herhangi bir ürün veya kayıt bulunamadı.",
                "image_urls": [],
                "process_log": [f"SQL ({sql_query}) döndürdü: 0 sonuç"]
            }

        # Step 4: Summarize the results back to user
        data_preview = json.dumps(data, ensure_ascii=False, default=str)
        # Limit data size passed to the prompt if it's too large
        if len(data_preview) > 8000:
            data_preview = data_preview[:8000] + "... (truncated)"
            
        summary_prompt = f"""
        You are a Helpful AI Data Assistant.
        The user asked: "{user_message}"
        
        Here is the raw data result from the database based on their request:
        {data_preview}
        
        Please provide a friendly, structured answer directly to the user detailing the findings. 
        If it's a list of products, summarize them clearly with bullet points, including name, brand, price, and stats like favorites if relevant.
        Make it easy to read. Be objective, rely ONLY on the data provided.
        """
        
        final_response = openai_client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.3
        )
        
        final_content = final_response.choices[0].message.content
        return {
            "content": final_content,
            "image_urls": [],
            "process_log": [f"Direct DB query executed. Results: {len(data)}"]
        }
        
    except Exception as e:
        logger.error(f"DATABASE_QUERY Error: {e}")
        return {
            "content": f"Veritabanı sorgusu sırasına bir hata oluştu: {str(e)}",
            "image_urls": [],
            "process_log": [str(e)]
        }
