from langchain_core.tools import tool
from app.repositories.menu_repository import MenuRepository
from app.models.menu_item import MenuItem
from app.core.database import SessionLocal
from app.my_agent.tools.faq_tools import get_embedding 
from app.core.config import settings
from langchain_openai import ChatOpenAI
from openai import OpenAI
# Using the repository instance
menu_repository = MenuRepository(MenuItem)


client=OpenAI(api_key=settings.OPENAI_API_KEY)

def create_menu_tools():

    @tool
    def get_menu_item_by_name(item_name: str):
        """Retrieve a specific menu item's details by its exact or closest matching name."""
        with SessionLocal() as db:
            item = menu_repository.search_item_by_name(db, item_name=item_name)
            if not item:
                return f"No item found matching '{item_name}'."
            
            return {
                "id": item.item_id,
                "name": item.item_name,
                "description": item.item_description,
                "price": float(item.item_price),
                "image_url": item.item_image
            }

    @tool
    def get_items_by_category(category: str):
        """Retrieve all menu items belonging to a specific category (e.g., 'Dessert', 'Main')."""
        with SessionLocal() as db:
            items = menu_repository.get_items_by_category(db, category=category)
            if not items:
                return f"No items found in the category: {category}."
            
            return [
                {
                    "id": i.item_id,
                    "name": i.item_name,
                    "price": float(i.item_price)
                } for i in items
            ]

    @tool
    def search_menu_by_keyword(keyword: str):
        """
        Search the menu for items matching a keyword in their name or description.
        Use this for keyword-specific queries like 'chicken', 'pasta', or 'vegan'.
        """
        with SessionLocal() as db:
            items = menu_repository.search_items_by_keyword(db, keyword=keyword)
            if not items:
                return "No items found matching that keyword."
        
            return [
                {
                    "id": item.item_id,
                    "name": item.item_name,
                    "price": float(item.item_price),
                    "description": item.item_description
                } for item in items
            ]

    @tool
    def search_menu_semantically(query: str):
        """
        Search for items by flavor, mood, or craving (e.g., 'something spicy', 'comfort food').
        """
        with SessionLocal() as db:
            items = menu_repository.get_all_items(db)
            if not items: 
                return "The menu is currently empty."

            # Prepare text for batch embedding
            texts = [f"{i.item_name}: {i.item_description or ''}" for i in items]
            
            # Batch API Call for efficiency
            response = client.embeddings.create(model="text-embedding-3-small", input=texts)
            menu_embeddings = [d.embedding for d in response.data]
            user_embedding = get_embedding(query)

            # Mathematical similarity ranking via repository
            matches = menu_repository.find_top_semantic_matches(user_embedding, items, menu_embeddings)
            
            return [
                {
                    "id": m[1].item_id,
                    "name": m[1].item_name, 
                    "price": float(m[1].item_price), 
                    "description": m[1].item_description
                } for m in matches
            ]

    @tool
    def get_affordable_items(budget: float):
        """
        Find menu items that cost less than or equal to the price (budget) provided.
        """
        with SessionLocal() as db:
            items = menu_repository.filter_by_max_price(db, budget)
            if not items: 
                return f"Nothing found on the menu under ${budget}."
            
            return [
                {
                    "id": i.item_id,
                    "name": i.item_name, 
                    "price": float(i.item_price)
                } for i in items
            ]

    return [
        get_menu_item_by_name,
        get_items_by_category,
        search_menu_by_keyword,
        search_menu_semantically,
        get_affordable_items
    ]