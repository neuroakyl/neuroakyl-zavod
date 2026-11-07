# Единый «лук» (STYLE LOCK) — консистентность всего ролика

Главная причина, почему кадры «не похожи»: каждый кадр описан по-новому. Решение из практики 2026 (character sheets + style block + элементы): **зафиксировать общий вид ОДИН раз** и наследовать его во всех кадрах, а в промпте кадра писать только то, что в нём **уникально**.

## Что фиксируем один раз (в шапке раскадровки)
1. **STYLE LOCK (визуальный стандарт):** плёнка/грейд, объективная линза-семейство, зерно, эпоха, общий уровень реализма. Пример: `Look: shot on ARRI Alexa, Kodak Vision3, natural directional light, fine film grain, grounded historical realism.`
2. **PALETTE / LIGHT LOGIC:** палитра и логика света (герой тёплый ↔ злодей холодный; арка света ролика).
3. **LOCATION LOCK:** где происходит (одна локация/сезон на весь ролик или чёткая арка).
4. **ELEMENTS (каст):** список тегов персонажей/предметов/локаций (`hero`, `rival`, `river`). Эти теги ставим в КАЖДЫЙ кадр, где они есть, и НЕ переописываем облик.
5. **ГЛОССАРИЙ незнакомого:** если предмет/явление не общеизвестно (жай-таш, ритуал жайчылык), опиши его ЗДЕСЬ один раз ясно — в кадрах только ссылайся, не пересказывай заново.

## Что пишем в промпте КАЖДОГО кадра (только уникальное)
- Теги нужных элементов.
- Что происходит (действие/поза/событие).
- Композиция + ракурс + один проезд камеры (киноязык).
- Локальный свет кадра (если отличается от общего) и 3 детали.
- НЕ повторяем: облик элементов, общий грейд/плёнку (они в STYLE LOCK), соотношение сторон, «no text/logos».

## Правило наследования
Каждый кадр = STYLE LOCK (по умолчанию) + уникальная дельта кадра. Так все кадры выглядят из одного фильма. Если для кадра нужно отклонение от лука — пиши явно только это отклонение.

## Пример шапки
```
STYLE LOCK: shot on ARRI Alexa, Kodak Vision3, natural directional light, fine film grain,
grounded historical realism, medium-format depth.
PALETTE/LIGHT: warm summer green → violet-black storm → cold blue → returning gold.
LOCATION LOCK: open steppe battlefield at the foot of the Ala-Too, a churning river nearby.
ELEMENTS: hero (masked, sabre) · rival · river.
GLOSSARY: @Jai_Tash — a smooth jade-green bezoar-like weather stone carved with faint runes
that glow cold silver when wet; the jaichylyk ritual = the stone is dipped in water and a
whisper summons a sudden storm.
```
