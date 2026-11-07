// Рендер карусели: slides.json + template.html -> out/slide-NN.png (1080x1350)
// Запуск:  node render.js [slides.json] [out]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const dataPath = path.resolve(process.argv[2] || 'slides.json');
  const outDir   = path.resolve(process.argv[3] || 'out');
  const tpl      = path.resolve(__dirname, 'template.html');

  const data = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1200, height: 1400 } });

  // прокидываем данные ДО загрузки страницы
  await page.addInitScript((d) => { window.__SLIDES__ = d; }, data);
  await page.goto('file://' + tpl.replace(/\\/g, '/'));

  // ждём шрифты (Google Fonts), иначе слайды отрендерятся дефолтным шрифтом
  try { await page.evaluate(() => document.fonts.ready); } catch (e) {}
  await page.waitForTimeout(600);

  const slides = await page.$$('.slide');
  let i = 0;
  for (const s of slides) {
    i++;
    const file = path.join(outDir, `slide-${String(i).padStart(2, '0')}.png`);
    await s.screenshot({ path: file });
    console.log('✓', path.basename(file));
  }
  await browser.close();
  console.log(`\nГотово: ${i} слайдов -> ${outDir}`);
})();
