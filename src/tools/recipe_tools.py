import logging
import traceback
from typing import Any, Dict, List, Optional, Union

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher
from models.recipe import Recipe, RecipeIngredient, RecipeInstruction
from pydantic import ValidationError

logger = logging.getLogger("mealie-mcp")


def register_recipe_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all recipe-related tools with the MCP server."""

    @mcp.tool()
    def get_recipes(
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Provides a paginated list of recipes with optional filtering.

        Args:
            search: Filters recipes by name or description.
            page: Page number for pagination.
            per_page: Number of items per page.
            categories: Filter by specific recipe categories.
            tags: Filter by specific recipe tags.

        Returns:
            Dict[str, Any]: Recipe summaries with details like ID, name, description, and image information.
        """
        try:
            logger.info(
                {
                    "message": "Fetching recipes",
                    "search": search,
                    "page": page,
                    "per_page": per_page,
                    "categories": categories,
                    "tags": tags,
                }
            )
            return mealie.get_recipes(
                search=search,
                page=page,
                per_page=per_page,
                categories=categories,
                tags=tags,
            )
        except Exception as e:
            error_msg = f"Error fetching recipes: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def get_recipe_detailed(slug: str) -> Dict[str, Any]:
        """Retrieve a specific recipe by its slug identifier. Use this when to get full recipe
        details for tasks like updating or displaying the recipe.

        Args:
            slug: The unique text identifier for the recipe, typically found in recipe URLs
                or from get_recipes results.

        Returns:
            Dict[str, Any]: Comprehensive recipe details including ingredients, instructions,
                nutrition information, notes, and associated metadata.
        """
        try:
            logger.info({"message": "Fetching recipe", "slug": slug})
            return mealie.get_recipe(slug)
        except Exception as e:
            error_msg = f"Error fetching recipe with slug '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def get_recipe_concise(slug: str) -> Dict[str, Any]:
        """Retrieve a concise version of a specific recipe by its slug identifier. Use this when you only
        need a summary of the recipe, such as for when mealplaning.

        Args:
            slug: The unique text identifier for the recipe, typically found in recipe URLs
                or from get_recipes results.

        Returns:
            Dict[str, Any]: Concise recipe summary with essential fields.
        """
        try:
            logger.info({"message": "Fetching recipe", "slug": slug})
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            return recipe.model_dump(
                include={
                    "name",
                    "slug",
                    "recipeServings",
                    "recipeYieldQuantity",
                    "recipeYield",
                    "totalTime",
                    "rating",
                    "recipeIngredient",
                    "lastMade",
                },
                exclude_none=True,
            )
        except Exception as e:
            error_msg = f"Error fetching recipe with slug '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def create_recipe(
        name: str, ingredients: List[str], instructions: List[str]
    ) -> Dict[str, Any]:
        """Create a new recipe

        Args:
            name: The name of the new recipe to be created.
            ingredients: A list of ingredients for the recipe including quantities and units.
            instructions: A list of instructions for preparing the recipe.

        Returns:
            Dict[str, Any]: The created recipe details.
        """
        try:
            logger.info({"message": "Creating recipe", "name": name})
            slug = mealie.create_recipe(name)
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            recipe.recipeIngredient = [RecipeIngredient(note=i) for i in ingredients]
            recipe.recipeInstructions = [
                RecipeInstruction(text=i) for i in instructions
            ]
            return mealie.update_recipe(slug, recipe.model_dump(exclude_none=True))
        except Exception as e:
            error_msg = f"Error creating recipe '{name}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def update_recipe_ingredients(
        slug: str,
        ingredients: List[str],
    ) -> Dict[str, Any]:
        """Replaces the ingredients of an existing recipe.

        Call this before updating instructions so Mealie can generate ingredient
        reference IDs that can be used in instruction ingredientReferences.

        Args:
            slug: The unique text identifier for the recipe to be updated.
            ingredients: A list of ingredients for the recipe including quantities and units.

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Updating recipe ingredients", "slug": slug})
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            recipe.recipeIngredient = [RecipeIngredient(note=i) for i in ingredients]
            return mealie.update_recipe(slug, recipe.model_dump(exclude_none=True))
        except Exception as e:
            error_msg = f"Error updating recipe ingredients '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def update_recipe_instructions(
        slug: str, instructions: List[Union[RecipeInstruction, str, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Replaces the instructions of an existing recipe.

        Provide ingredientReferences using the reference IDs generated after updating
        ingredients with update_recipe_ingredients.

        Args:
            slug: The unique text identifier for the recipe to be updated.
            instructions: A list of instruction objects with `text` (str) and optional
                `ingredientReferences` (List[str]) that should link back to ingredient
                reference IDs on the recipe. Raw strings are accepted for simple steps,
                and dictionary representations matching the RecipeInstruction schema are
                also supported.

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Updating recipe instructions", "slug": slug})
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            valid_refs = {
                ingredient.referenceId
                for ingredient in recipe.recipeIngredient
                if ingredient.referenceId
            }
            parsed_instructions: List[RecipeInstruction] = []
            for instruction in instructions:
                if isinstance(instruction, RecipeInstruction):
                    parsed_instructions.append(instruction)
                elif isinstance(instruction, str):
                    parsed_instructions.append(RecipeInstruction(text=instruction))
                elif isinstance(instruction, dict):
                    parsed_instructions.append(
                        RecipeInstruction.model_validate(instruction)
                    )
                else:
                    raise ToolError(
                        f"Instruction entries must be strings, RecipeInstruction models, or dicts; received {type(instruction).__name__}"
                    )
            for instr in parsed_instructions:
                unknown_refs = [
                    ref for ref in instr.ingredientReferences if ref not in valid_refs
                ]
                if unknown_refs and valid_refs:
                    raise ToolError(
                        f"Invalid ingredientReferences for recipe '{slug}': {unknown_refs}"
                    )
                if unknown_refs and not valid_refs:
                    raise ToolError(
                        f"No ingredient reference IDs present on recipe '{slug}'. "
                        "Call update_recipe_ingredients before adding instructions with ingredientReferences."
                    )
            recipe.recipeInstructions = parsed_instructions
            return mealie.update_recipe(slug, recipe.model_dump(exclude_none=True))
        except ValidationError as e:
            error_msg = (
                f"Invalid instruction format for recipe '{slug}': {e.errors()}"
            )
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Validation traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)
        except Exception as e:
            error_msg = f"Error updating recipe instructions '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)
