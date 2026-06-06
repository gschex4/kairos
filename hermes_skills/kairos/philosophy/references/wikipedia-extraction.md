# Wikipedia API Extraction for WC 2026 Data

## Why not just scrape the page?
The Wikipedia article for 2026 FIFA World Cup is ~14,000+ lines of accessibility-tree output. The browser snapshot tool truncates badly. The page also eats memory when you try `document.body.innerHTML`.

## Better approach: MediaWiki API from browser_console

### 1. Discover section numbers
```javascript
fetch('https://en.wikipedia.org/w/api.php?action=parse&page=2026_FIFA_World_Cup&prop=sections&format=json')
  .then(r => r.json())
  .then(d => {
    const sects = d.parse.sections.filter(s => s.line.includes('Group'));
    return sects.map(s => s.index + ' - ' + s.line + ': ' + s.number);
  })
```

Expected result (verified Jun 5, 2026):
```
14 - Group stage: 8
15 - Group A: 8.1
16 - Group B: 8.2
17 - Group C: 8.3
...
26 - Group L: 8.12
```

### 2. Fetch individual group tables
```javascript
fetch('https://en.wikipedia.org/w/api.php?action=parse&page=2026_FIFA_World_Cup&prop=text&section=15&format=json')
  .then(r => r.json())
  .then(d => d.parse.text['*'])
```

Returns HTML with a wikitable containing team rows. Team names are in `<a href="/wiki/TeamName" title="Team Name">TeamName</a>` links.

### 3. Extract match schedule
The schedule section is usually section 13 (index may shift). Fetch similarly:
```javascript
fetch('https://en.wikipedia.org/w/api.php?action=parse&page=2026_FIFA_World_Cup&prop=text&section=13&format=json')
```

### Pitfalls
- The HTML inside each section floods with inline CSS/style tags. Strip or ignore them.
- Don't use `execute_code` with urllib — Wikipedia API blocks Python's default User-Agent (403). The browser console works because it sends the browser's User-Agent.
- On Windows, avoid piping complex JavaScript through terminal commands; special chars (`|`, `&`, `<`, `>`) get intercepted by cmd.exe. Use browser_console for JS queries.
