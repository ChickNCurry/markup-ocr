import io
from typing import List

import matplotlib.pyplot as plt
from PIL import Image

from src.application.models import IRenderer


class LatexSymbolRenderer(IRenderer):
    def render_markup(self, markups: List[str]) -> List[Image.Image]:
        images = []

        for m in markups:
            img_buffer = io.BytesIO()

            try:
                plt.figure()
                plt.axis("off")
                plt.text(0.5, 0.5, f"${m}$", size=200, ha="center", va="center")
                plt.savefig(img_buffer, format="png")
                plt.close()
            except Exception:
                plt.figure()
                plt.axis("off")
                plt.text(
                    0.5,
                    0.5,
                    "Error",
                    size=100,
                    ha="center",
                    va="center",
                )
                plt.savefig(img_buffer, format="png")
                plt.close()

            image = Image.open(img_buffer)
            images.append(image)

        return images
