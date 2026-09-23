export type Product = { id:number; name:string; description:string; price:number; image:string; category:'Home'|'Accessories' };
export const products: Product[] = [
  {
    "id": 43,
    "name": "Decoration Swing",
    "description": "The Decoration Swing is a charming addition to your home decor. Crafted with intricate details, it adds a touch of elegance and whimsy to any room.",
    "price": 899,
    "image": "/products/43.webp",
    "category": "Home"
  },
  {
    "id": 44,
    "name": "Family Tree Photo Frame",
    "description": "The Family Tree Photo Frame is a sentimental and stylish way to display your cherished family memories. With multiple photo slots, it tells the story of your loved ones.",
    "price": 1299,
    "image": "/products/44.webp",
    "category": "Home"
  },
  {
    "id": 45,
    "name": "House Showpiece Plant",
    "description": "The House Showpiece Plant is an artificial plant that brings a touch of nature to your home without the need for maintenance. It adds greenery and style to any space.",
    "price": 699,
    "image": "/products/45.webp",
    "category": "Home"
  },
  {
    "id": 46,
    "name": "Plant Pot",
    "description": "The Plant Pot is a stylish container for your favorite plants. With a sleek design, it complements your indoor or outdoor garden, adding a modern touch to your plant display.",
    "price": 1499,
    "image": "/products/46.webp",
    "category": "Home"
  },
  {
    "id": 47,
    "name": "Table Lamp",
    "description": "The Table Lamp is a functional and decorative lighting solution for your living space. With a modern design, it provides both ambient and task lighting, enhancing the atmosphere.",
    "price": 999,
    "image": "/products/47.webp",
    "category": "Home"
  },
  {
    "id": 93,
    "name": "Brown Leather Belt Watch",
    "description": "The Brown Leather Belt Watch is a stylish timepiece with a classic design. Featuring a genuine leather strap and a sleek dial, it adds a touch of sophistication to your look.",
    "price": 1899,
    "image": "/products/93.webp",
    "category": "Accessories"
  },
  {
    "id": 94,
    "name": "Longines Master Collection",
    "description": "The Longines Master Collection is an elegant and refined watch known for its precision and craftsmanship. With a timeless design, it's a symbol of luxury and sophistication.",
    "price": 3499,
    "image": "/products/94.webp",
    "category": "Accessories"
  },
  {
    "id": 154,
    "name": "Black Sun Glasses",
    "description": "The Black Sun Glasses are a classic and stylish choice, featuring a sleek black frame and tinted lenses. They provide both UV protection and a fashionable look.",
    "price": 999,
    "image": "/products/154.webp",
    "category": "Accessories"
  },
  {
    "id": 155,
    "name": "Classic Sun Glasses",
    "description": "The Classic Sun Glasses offer a timeless design with a neutral frame and UV-protected lenses. These sunglasses are versatile and suitable for various occasions.",
    "price": 1199,
    "image": "/products/155.webp",
    "category": "Accessories"
  },
  {
    "id": 156,
    "name": "Green and Black Glasses",
    "description": "The Green and Black Glasses feature a bold combination of green and black colors, adding a touch of vibrancy to your eyewear collection. They are both stylish and eye-catching.",
    "price": 1299,
    "image": "/products/156.webp",
    "category": "Accessories"
  },
  {
    "id": 172,
    "name": "Blue Women's Handbag",
    "description": "The Blue Women's Handbag is a stylish and spacious accessory for everyday use. With a vibrant blue color and multiple compartments, it combines fashion and functionality.",
    "price": 1799,
    "image": "/products/172.webp",
    "category": "Accessories"
  },
  {
    "id": 173,
    "name": "Heshe Women's Leather Bag",
    "description": "The Heshe Women's Leather Bag is a luxurious and high-quality leather bag for the sophisticated woman. With a timeless design and durable craftsmanship, it's a versatile accessory.",
    "price": 2499,
    "image": "/products/173.webp",
    "category": "Accessories"
  },
  {
    "id": 175,
    "name": "White Faux Leather Backpack",
    "description": "The White Faux Leather Backpack is a trendy and practical backpack for the modern woman. With a sleek white design and ample storage space, it's perfect for both casual and on-the-go styles.",
    "price": 2199,
    "image": "/products/175.webp",
    "category": "Accessories"
  }
];
export const money = (n:number) => "₹" + n.toLocaleString("en-IN");
