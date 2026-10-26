"""Report the pixel extent of a screenshot difference using the installed browser."""
import asyncio
import base64
from pathlib import Path
import sys

from playwright.async_api import async_playwright


async def main():
    left, right = (Path(value) for value in sys.argv[1:3])
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        result = await page.evaluate("""async ({left, right}) => {
          async function pixels(uri) {
            const image = new Image();
            image.src = uri;
            await image.decode();
            const canvas = document.createElement('canvas');
            canvas.width = image.width;
            canvas.height = image.height;
            const context = canvas.getContext('2d');
            context.drawImage(image, 0, 0);
            return {width:image.width, height:image.height,
              data:context.getImageData(0, 0, image.width, image.height).data};
          }
          const a = await pixels(left), b = await pixels(right);
          if (a.width !== b.width || a.height !== b.height)
            return {a:[a.width,a.height], b:[b.width,b.height], dimensionsDiffer:true};
          let count=0, minX=a.width, minY=a.height, maxX=-1, maxY=-1;
          for (let y=0; y<a.height; y++) for (let x=0; x<a.width; x++) {
            const i=(y*a.width+x)*4;
            if (a.data[i]!==b.data[i] || a.data[i+1]!==b.data[i+1] ||
                a.data[i+2]!==b.data[i+2] || a.data[i+3]!==b.data[i+3]) {
              count++; minX=Math.min(minX,x); minY=Math.min(minY,y);
              maxX=Math.max(maxX,x); maxY=Math.max(maxY,y);
            }
          }
          const sample = (x,y) => {
            const i=(y*a.width+x)*4;
            return {at:[x,y],a:Array.from(a.data.slice(i,i+4)),
              b:Array.from(b.data.slice(i,i+4))};
          };
          return {size:[a.width,a.height], differentPixels:count,
            bounds:count?[minX,minY,maxX,maxY]:null,
            samples:count?[sample(minX,minY),sample(Math.floor((minX+maxX)/2),Math.floor((minY+maxY)/2))]:[]};
        }""", {
            "left": "data:image/png;base64," + base64.b64encode(left.read_bytes()).decode(),
            "right": "data:image/png;base64," + base64.b64encode(right.read_bytes()).decode(),
        })
        print(result)
        await browser.close()


asyncio.run(main())
