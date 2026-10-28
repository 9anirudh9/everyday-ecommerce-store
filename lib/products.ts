type BaseProduct = { id:number; name:string; description:string; price:number; image:string; category:'Home'|'Accessories' };
export type Product = BaseProduct & {
  stock:number;
  images:string[];
  rating:number;
  nameFr?:string;
  descriptionFr?:string;
  variantGroup?:string;
  variantLabel?:string;
};
const legacyProducts: BaseProduct[] = [
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

// Demo inventory is deterministic reference data, not a live warehouse feed.
// Legacy catalog identifiers, text, prices and primary images above stay intact.
const newProductSeeds: Array<Omit<Product,'image'|'images'|'descriptionFr'>> = [
  {id:200,name:'Everyday Ceramic Mug — Sage',nameFr:'Tasse en céramique — sauge',description:'A 300 ml glazed ceramic mug with a comfortable handle and a soft sage finish. Hand wash recommended.',price:549,category:'Home',stock:16,rating:4.7,variantGroup:'ceramic-mug',variantLabel:'Sage'},
  {id:201,name:'Everyday Ceramic Mug — Sand',nameFr:'Tasse en céramique — sable',description:'A 300 ml glazed ceramic mug with a comfortable handle and a warm sand finish. Hand wash recommended.',price:549,category:'Home',stock:2,rating:4.7,variantGroup:'ceramic-mug',variantLabel:'Sand'},
  {id:202,name:'Ribbed Glass Vase',nameFr:'Vase en verre strié',description:'A 24 cm ribbed glass vase for a small bouquet or dried stems. Its clear finish suits a shelf or dining table.',price:1199,category:'Home',stock:0,rating:4.5},
  {id:203,name:'Linen Cushion — Olive',nameFr:'Coussin en lin — olive',description:'A soft 40 × 40 cm cushion with a removable linen-blend cover and concealed zip. Includes a lightweight insert.',price:899,category:'Home',stock:12,rating:4.4,variantGroup:'linen-cushion',variantLabel:'Olive · 40 cm'},
  {id:204,name:'Woven Storage Basket',nameFr:'Panier de rangement tressé',description:'A compact woven basket with two handles for throws, magazines or everyday essentials. Approximately 30 cm wide.',price:1299,category:'Home',stock:8,rating:4.6},
  {id:205,name:'Oak Desk Organiser',nameFr:'Organiseur de bureau en chêne',description:'A three-compartment desk organiser with a natural wood finish, sized for pens, notes and small accessories.',price:999,category:'Home',stock:14,rating:4.5},
  {id:206,name:'Amber Candle Jar',nameFr:'Bougie en pot ambré',description:'A 180 g decorative candle in a reusable amber jar, with a subtle cedar-inspired scent. Never leave a lit candle unattended.',price:649,category:'Home',stock:20,rating:4.3},
  {id:207,name:'Cotton Table Runner',nameFr:'Chemin de table en coton',description:'A 35 × 140 cm cotton table runner in a neutral natural weave. Machine wash gently and dry flat.',price:799,category:'Home',stock:9,rating:4.2},
  {id:208,name:'Stoneware Serving Bowl',nameFr:'Saladier en grès',description:'A 22 cm stoneware serving bowl with a glazed interior and a tactile matte outer finish. Suitable for everyday dining.',price:1499,category:'Home',stock:7,rating:4.8},
  {id:209,name:'Minimal Wall Clock',nameFr:'Horloge murale minimaliste',description:'A 28 cm wall clock with a simple face and clear hands. Requires one AA battery, not included.',price:1899,category:'Home',stock:11,rating:4.4},
  {id:210,name:'Botanical Print Set',nameFr:'Lot d’affiches botaniques',description:'Three A4 botanical art prints on matte paper. Display together or individually; frames are not included.',price:699,category:'Home',stock:18,rating:4.6},
  {id:211,name:'Recycled Glass Carafe',nameFr:'Carafe en verre recyclé',description:'A 750 ml glass carafe for water or cold drinks. Small variations in the glass give each piece its character.',price:999,category:'Home',stock:6,rating:4.5},
  {id:212,name:'Soft Cotton Throw',nameFr:'Plaid doux en coton',description:'A light 120 × 150 cm cotton throw with a fringed edge, ideal for a reading chair or the end of a bed.',price:1799,category:'Home',stock:10,rating:4.7},
  {id:213,name:'Bamboo Plant Stand',nameFr:'Support de plante en bambou',description:'A compact bamboo stand for a plant pot up to 20 cm in diameter. Use indoors on a flat surface.',price:1299,category:'Home',stock:5,rating:4.4},
  {id:214,name:'Brass Photo Holder',nameFr:'Porte-photo en laiton',description:'A small brass-tone photo holder for a favourite postcard, print or note. Its weighted base keeps the display upright.',price:399,category:'Home',stock:24,rating:4.1},
  {id:215,name:'Canvas Crossbody Bag',nameFr:'Sac bandoulière en toile',description:'A compact cotton-canvas bag with an adjustable strap, zipped main compartment and a small inside pocket.',price:1399,category:'Accessories',stock:15,rating:4.6},
  {id:216,name:'Round Acetate Sunglasses',nameFr:'Lunettes rondes en acétate',description:'Lightweight round sunglasses with a smooth acetate-style frame. Includes a soft drawstring pouch.',price:1099,category:'Accessories',stock:12,rating:4.3},
  {id:217,name:'Everyday Digital Watch',nameFr:'Montre numérique du quotidien',description:'An easy-read digital watch with an adjustable silicone strap, date display and simple daily alarm.',price:1699,category:'Accessories',stock:8,rating:4.5},
  {id:218,name:'Travel Jewellery Pouch',nameFr:'Pochette à bijoux de voyage',description:'A softly lined zip pouch with separate pockets for small jewellery and keepsakes. Designed for light travel.',price:699,category:'Accessories',stock:0,rating:4.4},
  {id:219,name:'Slim Card Wallet',nameFr:'Porte-cartes fin',description:'A slim card wallet with four card slots and a central pocket for folded notes. Fits comfortably in a jacket pocket.',price:599,category:'Accessories',stock:19,rating:4.2},
  {id:220,name:'Cotton Weekend Scarf',nameFr:'Foulard de week-end en coton',description:'A breathable 60 × 180 cm cotton scarf with a light woven texture and a gently fringed edge.',price:899,category:'Accessories',stock:10,rating:4.5},
  {id:221,name:'Woven Key Loop',nameFr:'Porte-clés tissé',description:'A sturdy woven key loop with a metal split ring, sized to find easily in a tote or backpack.',price:249,category:'Accessories',stock:30,rating:4.0},
  {id:222,name:'Compact Travel Backpack',nameFr:'Sac à dos de voyage compact',description:'A lightweight day backpack with padded straps, two zip compartments and an outer bottle pocket. Approximately 12 litres.',price:2299,category:'Accessories',stock:6,rating:4.7},
  {id:223,name:'Classic Leather Belt',nameFr:'Ceinture classique en cuir',description:'A simple 30 mm leather belt with a brushed metal buckle. Its 105 cm strap can be trimmed to fit.',price:1199,category:'Accessories',stock:9,rating:4.4},
  {id:224,name:'Linen Cushion — Natural',nameFr:'Coussin en lin — naturel',description:'A soft 40 × 40 cm cushion with a removable natural linen-blend cover and concealed zip. Includes a lightweight insert.',price:899,category:'Home',stock:14,rating:4.4,variantGroup:'linen-cushion',variantLabel:'Natural · 40 cm'},
  {id:225,name:'Linen Cushion — Large Natural',nameFr:'Grand coussin en lin — naturel',description:'A generous 50 × 50 cm cushion with a removable natural linen-blend cover and concealed zip. Includes an insert.',price:1199,category:'Home',stock:4,rating:4.6,variantGroup:'linen-cushion',variantLabel:'Natural · 50 cm'},
  {id:226,name:'Everyday Tote — Forest',nameFr:'Sac cabas — forêt',description:'A reusable cotton-canvas tote in forest green, with long handles and a roomy 38 × 40 cm main compartment.',price:799,category:'Accessories',stock:16,rating:4.8,variantGroup:'everyday-tote',variantLabel:'Forest'},
  {id:227,name:'Everyday Tote — Sand',nameFr:'Sac cabas — sable',description:'A reusable cotton-canvas tote in warm sand, with long handles and a roomy 38 × 40 cm main compartment.',price:799,category:'Accessories',stock:13,rating:4.8,variantGroup:'everyday-tote',variantLabel:'Sand'},
  {id:228,name:'Ceramic Soap Dish',nameFr:'Porte-savon en céramique',description:'A glazed ceramic soap dish with raised ridges that help a soap bar drain between uses. Approximately 12 cm wide.',price:449,category:'Home',stock:17,rating:4.3},
  {id:229,name:'Pocket Notebook Trio',nameFr:'Trio de carnets de poche',description:'Three A6 notebooks with stitched bindings and plain recycled-paper pages, ready for notes, lists and small sketches.',price:349,category:'Accessories',stock:22,rating:4.2},
];

const frenchDescriptions:Record<number,string>={
  200:'Une tasse en céramique émaillée de 300 ml avec une anse confortable et une finition sauge. Lavage à la main conseillé.',
  201:'Une tasse en céramique émaillée de 300 ml avec une anse confortable et une finition sable. Lavage à la main conseillé.',
  202:'Un vase en verre strié de 24 cm pour un petit bouquet ou des fleurs séchées, à poser sur une étagère ou une table.',
  203:'Un coussin de 40 × 40 cm avec une housse amovible en mélange de lin olive et une fermeture discrète. Garnissage inclus.',
  204:'Un panier tressé compact avec deux anses pour les plaids, les magazines et les petits objets. Largeur d’environ 30 cm.',
  205:'Un organiseur de bureau à trois compartiments, en finition bois naturel, pour les stylos, les notes et les petits accessoires.',
  206:'Une bougie décorative de 180 g dans un pot ambré réutilisable, au parfum léger inspiré du cèdre. Ne jamais laisser une bougie allumée sans surveillance.',
  207:'Un chemin de table en coton de 35 × 140 cm, au tissage naturel. Lavage doux en machine et séchage à plat.',
  208:'Un saladier en grès de 22 cm, avec un intérieur émaillé et un extérieur mat, pour les repas du quotidien.',
  209:'Une horloge murale de 28 cm au cadran simple et lisible. Fonctionne avec une pile AA, non incluse.',
  210:'Trois affiches botaniques A4 sur papier mat, à exposer ensemble ou séparément. Cadres non inclus.',
  211:'Une carafe en verre de 750 ml pour l’eau et les boissons fraîches. De petites variations du verre lui donnent son caractère.',
  212:'Un plaid léger en coton de 120 × 150 cm, avec des bords frangés, pour un fauteuil de lecture ou le pied du lit.',
  213:'Un support compact en bambou pour un pot jusqu’à 20 cm de diamètre. À utiliser à l’intérieur sur une surface plane.',
  214:'Un petit porte-photo couleur laiton pour une carte, une affiche ou une note. Son socle lesté maintient le support droit.',
  215:'Un sac compact en toile de coton avec une bandoulière réglable, une fermeture zippée et une petite poche intérieure.',
  216:'Des lunettes de soleil rondes et légères, avec une monture lisse de style acétate. Pochette souple incluse.',
  217:'Une montre numérique lisible avec un bracelet réglable en silicone, l’affichage de la date et une alarme quotidienne.',
  218:'Une pochette zippée doublée, avec des poches séparées pour les petits bijoux et les souvenirs, pratique en voyage.',
  219:'Un porte-cartes fin avec quatre emplacements et une poche centrale pour les billets pliés, adapté à une poche de veste.',
  220:'Un foulard respirant en coton de 60 × 180 cm, au tissage léger et aux bords délicatement frangés.',
  221:'Un porte-clés tissé solide avec un anneau métallique, facile à retrouver dans un cabas ou un sac à dos.',
  222:'Un sac à dos léger d’environ 12 litres avec des bretelles rembourrées, deux compartiments zippés et une poche pour gourde.',
  223:'Une ceinture en cuir de 30 mm avec une boucle en métal brossé. Sa lanière de 105 cm peut être recoupée pour s’ajuster.',
  224:'Un coussin de 40 × 40 cm avec une housse amovible en mélange de lin naturel et une fermeture discrète. Garnissage inclus.',
  225:'Un grand coussin de 50 × 50 cm avec une housse amovible en mélange de lin naturel et une fermeture discrète. Garnissage inclus.',
  226:'Un cabas réutilisable en toile de coton vert forêt, avec de longues anses et un grand compartiment de 38 × 40 cm.',
  227:'Un cabas réutilisable en toile de coton couleur sable, avec de longues anses et un grand compartiment de 38 × 40 cm.',
  228:'Un porte-savon en céramique émaillée d’environ 12 cm, avec des rainures pour laisser sécher le savon entre deux utilisations.',
  229:'Trois carnets A6 à reliure cousue et pages unies en papier recyclé, pour les notes, les listes et les petits croquis.',
};

export const products: Product[] = [
  ...legacyProducts.map((product,index)=>({...product,stock:product.id===46?18:12+index,
    images:[product.image,`/products/${product.id}-detail.svg`],rating:Number((4.1+(index%8)/10).toFixed(1))})),
  ...newProductSeeds.map(product=>({...product,image:`/products/${product.id}.svg`,
    images:[`/products/${product.id}.svg`,`/products/${product.id}-detail.svg`],
    descriptionFr:frenchDescriptions[product.id]})),
];

export const money = (n:number) => "₹" + n.toLocaleString("en-IN");
