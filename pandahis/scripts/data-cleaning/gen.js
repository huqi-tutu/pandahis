// Data Cleaning Toolkit Generator
var fs=require("fs"),path=require("path");
var base=__dirname;
function w(n,c){var f=path.join(base,n);fs.mkdirSync(path.dirname(f),{recursive:true});fs.writeFileSync(f,c,"utf8");console.log("Wrote "+n);}

// -- Index Schema --
w("schemas/index-schema.mjs",[