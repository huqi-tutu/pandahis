import { spawnSync } from 'child_process';
const [zip, kw, out] = process.argv.slice(2);
const cmd = Add-Type -AssemblyName System.IO.Compression.FileSystem; =[System.IO.Compression.ZipFile]::OpenRead(''); foreach( in .Entries){if(.FullName.Contains('') -and .FullName.EndsWith('.json')){=.Open();=(New-Object System.IO.StreamReader()).ReadToEnd();[IO.File]::WriteAllText('',,[Text.Encoding]::UTF8);break}}; .Dispose();
const r = spawnSync('powershell', ['-Command', cmd], {encoding:'utf8', maxBuffer:100*1024*1024, timeout:30000});
if (r.error) { console.error(r.error.message); process.exit(1); }
if (r.stderr) console.error(r.stderr.slice(0,300));
console.log('Extracted ->', out);
