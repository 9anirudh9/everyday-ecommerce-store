/** Business contract checks; uses the project's existing TypeScript compiler. */
import assert from 'node:assert/strict';
import {readFileSync,existsSync,mkdirSync,writeFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {createRequire} from 'node:module';
import {runInThisContext} from 'node:vm';
import {execFileSync} from 'node:child_process';
import ts from 'typescript';

const root=resolve(import.meta.dirname,'..');
const nodeRequire=createRequire(import.meta.url);
const cache=new Map();
function load(path){
  const file=resolve(root,path);
  if(cache.has(file))return cache.get(file).exports;
  const loaded={exports:{}};
  cache.set(file,loaded);
  const compiled=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
  const wrapped=runInThisContext(`(function(exports,require,module,__filename,__dirname){${compiled}\n})`,{filename:file});
  wrapped(loaded.exports,specifier=>{
    if(!specifier.startsWith('.')&&!specifier.startsWith('@/'))return nodeRequire(specifier);
    const base=specifier.startsWith('@/')?resolve(root,specifier.slice(2)):resolve(dirname(file),specifier);
    return load(existsSync(base)?base:base+'.ts');
  },loaded,file,dirname(file));
  return loaded.exports;
}
const {products}=load('lib/products.ts');
const {parseCatalogQuery,selectCatalog,relatedProducts}=load('lib/catalog.ts');
const {searchProducts}=load('lib/search.ts');
const {maxProductQuantity,validateStockQuantity}=load('lib/stock.ts');
const records=[];
function check(name,test){
  try{test();records.push({name,status:'PASS'});console.log('PASS',name)}
  catch(error){records.push({name,status:'FAIL',error:error.stack});console.error('FAIL',name,error.message)}
}
const query=value=>{
  const parsed=parseCatalogQuery(new URLSearchParams(value));
  assert.equal(parsed.error,undefined);
  return parsed.query;
};
const result=value=>selectCatalog(query(value));

check('CAT-01 original 13 full legacy fields unchanged',()=>{
  const original=execFileSync('git',['show','723a86378323c4c098d29744a8dec7bcb6ef13a2:lib/products.ts'],{cwd:root,encoding:'utf8'});
  const legacy=JSON.parse(original.slice(original.indexOf('= [')+2,original.indexOf('];')+1));
  assert.equal(legacy.length,13);
  for(const expected of legacy){
    const actual=products.find(p=>p.id===expected.id);
    assert.ok(actual);
    for(const [key,value] of Object.entries(expected))assert.equal(actual[key],value,`${expected.id}.${key}`);
  }
});
check('CAT-10 expanded catalog has 43 unique immutable IDs',()=>{
  assert.equal(products.length,43);assert.equal(new Set(products.map(p=>p.id)).size,43);
  assert.equal(products.filter(p=>p.id>=200).length,30);
});
check('CAT-02 existing search case and whitespace equivalence',()=>{
  const ids=value=>searchProducts(value).map(p=>p.id);
  assert.deepEqual(ids('plant'),ids('PLANT'));assert.deepEqual(ids('plant'),ids('  plant  '));
  assert.ok(ids('plant').includes(46));
});
check('CAT-03 unknown query returns accessible-model empty result',()=>{
  const data=result('q=notarealproduct');assert.equal(data.total,0);assert.equal(data.items.length,0);assert.equal(data.totalPages,1);
});
check('CAT-04 combined category price stock rating filters use AND',()=>{
  const data=result('category=Home&minPrice=500&maxPrice=1000&inStock=true&rating=4.5');
  assert.ok(data.total>0);
  for(const p of data.items)assert.ok(p.category==='Home'&&p.price>=500&&p.price<=1000&&p.stock>0&&p.rating>=4.5);
});
check('CAT-04 price boundaries are inclusive and tied prices sort by ID',()=>{
  const data=result('minPrice=1499&maxPrice=1499&sort=price-asc');
  assert.deepEqual(data.items.map(p=>p.id),[46,208]);
});
check('CAT-04 ascending and descending price sorting are stable',()=>{
  for(const sort of ['price-asc','price-desc']){
    const all=[];
    for(let page=1;page<=5;page++)all.push(...result(`sort=${sort}&page=${page}`).items);
    for(let i=1;i<all.length;i++){
      assert.ok(sort==='price-asc'?all[i-1].price<=all[i].price:all[i-1].price>=all[i].price);
      if(all[i-1].price===all[i].price)assert.ok(all[i-1].id<all[i].id);
    }
  }
});
check('CAT-06 available-only excludes every zero-stock product',()=>{
  const data=result('inStock=true');assert.equal(data.total,41);
  const all=[];for(let page=1;page<=data.totalPages;page++)all.push(...result(`inStock=true&page=${page}`).items);
  assert.ok(all.every(p=>p.stock>0));assert.ok(!all.some(p=>p.id===202||p.id===218));
});
check('CAT-07 pagination preserves total and partial final page',()=>{
  assert.equal(result('').items.length,10);assert.equal(result('page=3').items.length,10);
  assert.equal(result('page=5').items.length,3);assert.equal(result('page=5').total,43);
  assert.equal(result('page=999').page,5);
  const ids=[];for(let page=1;page<=5;page++)ids.push(...result(`page=${page}`).items.map(p=>p.id));
  assert.equal(new Set(ids).size,43);
});
check('CAT-05 invalid range and malformed query reject deterministically',()=>{
  for(const value of ['minPrice=1000&maxPrice=500','minPrice=-1','maxPrice=banana','rating=6','page=1.5','category=invalid','sort=invalid'])assert.ok(parseCatalogQuery(new URLSearchParams(value)).error,value);
});
check('PDP-01 product 46 remains Plant Pot Home INR1499',()=>{
  const p=products.find(p=>p.id===46);assert.equal(p.name,'Plant Pot');assert.equal(p.category,'Home');assert.equal(p.price,1499);
});
check('PDP-02 stock quantity is integer 1..min(10,stock)',()=>{
  const normal=products.find(p=>p.id===46),low=products.find(p=>p.id===201);
  assert.equal(maxProductQuantity(normal),10);assert.equal(maxProductQuantity(low),2);
  for(const qty of [1,10])assert.equal(validateStockQuantity(normal,qty).valid,true);
  for(const qty of [-1,0,1.5,11])assert.equal(validateStockQuantity(normal,qty).valid,false);
  assert.equal(validateStockQuantity(low,3).valid,false);
});
check('PDP-04 out-of-stock products reject purchases',()=>{
  const p=products.find(p=>p.id===202);assert.equal(maxProductQuantity(p),0);assert.equal(validateStockQuantity(p,1).code,'OUT_OF_STOCK');
});
check('PDP-06 every primary and secondary image is a local existing asset',()=>{
  for(const p of products){assert.ok(p.images.length>=2);for(const image of p.images)assert.ok(existsSync(resolve(root,'public',image.slice(1))),image)}
});
check('PDP-09 related items exclude current ID and prefer selectable siblings',()=>{
  const p=products.find(p=>p.id===200),related=relatedProducts(p);
  assert.equal(related[0].id,201);assert.ok(related.every(item=>item.id!==200&&item.category===p.category));
});
check('PDP-03 variant choices are separate product IDs and preserve cart shape',()=>{
  const variants=products.filter(p=>p.variantGroup==='ceramic-mug');assert.equal(variants.length,2);
  assert.notEqual(variants[0].id,variants[1].id);assert.notEqual(variants[0].variantLabel,variants[1].variantLabel);
});
const output={scope:'Pure catalog and stock domain contracts; no browser/API execution',records,passed:records.filter(r=>r.status==='PASS').length,failed:records.filter(r=>r.status==='FAIL').length};
mkdirSync(resolve(root,'outputs/p0-02-03'),{recursive:true});
writeFileSync(resolve(root,'outputs/p0-02-03/domain-results.json'),JSON.stringify(output,null,2));
process.exitCode=output.failed?1:0;
