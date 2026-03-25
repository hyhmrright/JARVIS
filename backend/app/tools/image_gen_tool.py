"""Tool for generating images via OpenAI's DALL-E 3."""

from typing import Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class ImageGenInput(BaseModel):
    prompt: str = Field(description="A detailed description of the image to generate.")
    size: Literal["1024x1024"] = Field(
        default="1024x1024", description="The size of the generated image."
    )


class ImageGenTool(BaseTool):
    name: str = "image_gen"
    description: str = (
        "Generate an image based on a text prompt using DALL-E 3. "
        "Returns the URL of the generated image."
    )
    args_schema: type[BaseModel] = ImageGenInput
    openai_api_key: str

    def _run(self, prompt: str, size: str = "1024x1024") -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, prompt: str, size: str = "1024x1024") -> str:
        import openai

        if not self.openai_api_key:
            return "Error: OpenAI API key is required to generate images."

        try:
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)
            response = await client.images.generate(  # type: ignore[call-overload]
                model="dall-e-3",
                prompt=prompt,
                size=size,
                n=1,
            )
            if not response.data or not response.data[0].url:
                return "Error: Failed to generate image, no URL returned."
            return f"Image generated successfully: {response.data[0].url}"
        except Exception as e:
            return f"Error generating image: {e!s}"


def create_image_gen_tool(openai_api_key: str | None) -> BaseTool | None:
    if not openai_api_key:
        return None
    return ImageGenTool(openai_api_key=openai_api_key)
