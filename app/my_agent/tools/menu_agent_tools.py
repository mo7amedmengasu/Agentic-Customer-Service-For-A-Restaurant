from langchain_core.tools import tool
from app.repositories.menu_repository import MenuRepository
from app.models.menu_item import MenuItem
from app.core.database import SessionLocal
from app.my_agent.tools.faq_tools import get_embedding
from app.core.config import settings

# Using the repository instance
menu_repository = MenuRepository(MenuItem)

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
    def search_menu_by_keyword(keyword: str):
        """
        Search the menu for items where the keyword appears LITERALLY in the item name or description.
        Only use this when the user mentions a specific ingredient or dish type that would appear word-for-word
        in a menu listing (e.g. 'chicken', 'pasta', 'pizza', 'chocolate', 'vegan').
        Do NOT use for general food categories like 'meat', 'protein', 'healthy' — use search_menu_semantically instead.
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
        Search for menu items that best match a food preference, craving, mood, or concept.
        Use this when:
        - The user expresses a general food preference (e.g. 'I like meat', 'I enjoy grilled food', 'I want something sweet')
        - The exact word may NOT appear in item names/descriptions (e.g. 'meat' won't literally appear in 'Burger')
        - The user describes a mood or craving ('comfort food', 'something light', 'filling meal')
        This tool uses semantic similarity — always prefer it over search_menu_by_keyword for preference queries.
        """
        with SessionLocal() as db:
            user_embedding = get_embedding(query)
            matches = menu_repository.find_top_semantic_matches_from_db(db, user_embedding)

            if not matches:
                return "No menu items matched your preference."

            return [
                {
                    "id": m[1].item_id,
                    "name": m[1].item_name,
                    "price": float(m[1].item_price),
                    "description": m[1].item_description,
                }
                for m in matches
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

    @tool
    def get_all_menu_items():
        """
        Retrieve all available items on the menu.
        Use this when the user asks what is on the menu, what items are available, or wants a full menu listing.
        """
        with SessionLocal() as db:
            items = menu_repository.get_all_items(db)
            if not items:
                return "The menu is currently empty."
            return [
                {
                    "id": i.item_id,
                    "name": i.item_name,
                    "price": float(i.item_price),
                    "description": i.item_description
                } for i in items
            ]

    return [
        get_all_menu_items,
        get_menu_item_by_name,
        search_menu_by_keyword,
        search_menu_semantically,
        get_affordable_items
    ]