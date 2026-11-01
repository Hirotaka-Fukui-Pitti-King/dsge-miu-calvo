// Simple numbering for non-book documents
#let equation-numbering = "(1)"
#let callout-numbering = "1"
#let subfloat-numbering(n-super, subfloat-idx) = {
  numbering("1a", n-super, subfloat-idx)
}

// Theorem configuration for theorion
// Simple numbering for non-book documents (no heading inheritance)
#let theorem-inherited-levels = 0

// Theorem numbering format (can be overridden by extensions for appendix support)
// This function returns the numbering pattern to use
#let theorem-numbering(loc) = "1.1"

// Default theorem render function
#let theorem-render(prefix: none, title: "", full-title: auto, body) = {
  if full-title != "" and full-title != auto and full-title != none {
    strong[#full-title.]
    h(0.5em)
  }
  body
}
// Some definitions presupposed by pandoc's typst output.
#let content-to-string(content) = {
  if content.has("text") {
    content.text
  } else if content.has("children") {
    content.children.map(content-to-string).join("")
  } else if content.has("body") {
    content-to-string(content.body)
  } else if content == [ ] {
    " "
  }
}

#let horizontalrule = line(start: (25%,0%), end: (75%,0%))

#let endnote(num, contents) = [
  #stack(dir: ltr, spacing: 3pt, super[#num], contents)
]

#show terms.item: it => block(breakable: false)[
  #text(weight: "bold")[#it.term]
  #block(inset: (left: 1.5em, top: -0.4em))[#it.description]
]

// Some quarto-specific definitions.

#show raw.where(block: true): set block(
    fill: luma(230),
    width: 100%,
    inset: 8pt,
    radius: 2pt
  )

#let block_with_new_content(old_block, new_content) = {
  let fields = old_block.fields()
  let _ = fields.remove("body")
  if fields.at("below", default: none) != none {
    // TODO: this is a hack because below is a "synthesized element"
    // according to the experts in the typst discord...
    fields.below = fields.below.abs
  }
  block.with(..fields)(new_content)
}

#let empty(v) = {
  if type(v) == str {
    // two dollar signs here because we're technically inside
    // a Pandoc template :grimace:
    v.matches(regex("^\\s*$")).at(0, default: none) != none
  } else if type(v) == content {
    if v.at("text", default: none) != none {
      return empty(v.text)
    }
    for child in v.at("children", default: ()) {
      if not empty(child) {
        return false
      }
    }
    return true
  }

}

// Subfloats
// This is a technique that we adapted from https://github.com/tingerrr/subpar/
#let quartosubfloatcounter = counter("quartosubfloatcounter")

#let quarto_super(
  kind: str,
  caption: none,
  label: none,
  supplement: str,
  position: none,
  subcapnumbering: "(a)",
  body,
) = {
  context {
    let figcounter = counter(figure.where(kind: kind))
    let n-super = figcounter.get().first() + 1
    set figure.caption(position: position)
    [#figure(
      kind: kind,
      supplement: supplement,
      caption: caption,
      {
        show figure.where(kind: kind): set figure(numbering: _ => {
          let subfloat-idx = quartosubfloatcounter.get().first() + 1
          subfloat-numbering(n-super, subfloat-idx)
        })
        show figure.where(kind: kind): set figure.caption(position: position)

        show figure: it => {
          let num = numbering(subcapnumbering, n-super, quartosubfloatcounter.get().first() + 1)
          show figure.caption: it => block({
            num.slice(2) // I don't understand why the numbering contains output that it really shouldn't, but this fixes it shrug?
            [ ]
            it.body
          })

          quartosubfloatcounter.step()
          it
          counter(figure.where(kind: it.kind)).update(n => n - 1)
        }

        quartosubfloatcounter.update(0)
        body
      }
    )#label]
  }
}

// callout rendering
// this is a figure show rule because callouts are crossreferenceable
#show figure: it => {
  if type(it.kind) != str {
    return it
  }
  let kind_match = it.kind.matches(regex("^quarto-callout-(.*)")).at(0, default: none)
  if kind_match == none {
    return it
  }
  let kind = kind_match.captures.at(0, default: "other")
  kind = upper(kind.first()) + kind.slice(1)
  // now we pull apart the callout and reassemble it with the crossref name and counter

  // when we cleanup pandoc's emitted code to avoid spaces this will have to change
  let old_callout = it.body.children.at(1).body.children.at(1)
  let old_title_block = old_callout.body.children.at(0)
  let children = old_title_block.body.body.children
  let old_title = if children.len() == 1 {
    children.at(0)  // no icon: title at index 0
  } else {
    children.at(1)  // with icon: title at index 1
  }

  // TODO use custom separator if available
  // Use the figure's counter display which handles chapter-based numbering
  // (when numbering is a function that includes the heading counter)
  let callout_num = it.counter.display(it.numbering)
  let new_title = if empty(old_title) {
    [#kind #callout_num]
  } else {
    [#kind #callout_num: #old_title]
  }

  let new_title_block = block_with_new_content(
    old_title_block,
    block_with_new_content(
      old_title_block.body,
      if children.len() == 1 {
        new_title  // no icon: just the title
      } else {
        children.at(0) + new_title  // with icon: preserve icon block + new title
      }))

  align(left, block_with_new_content(old_callout,
    block(below: 0pt, new_title_block) +
    old_callout.body.children.at(1)))
}

// 2023-10-09: #fa-icon("fa-info") is not working, so we'll eval "#fa-info()" instead
#let callout(body: [], title: "Callout", background_color: rgb("#dddddd"), icon: none, icon_color: black, body_background_color: white) = {
  block(
    breakable: false, 
    fill: background_color, 
    stroke: (paint: icon_color, thickness: 0.5pt, cap: "round"), 
    width: 100%, 
    radius: 2pt,
    block(
      inset: 1pt,
      width: 100%, 
      below: 0pt, 
      block(
        fill: background_color,
        width: 100%,
        inset: 8pt)[#if icon != none [#text(icon_color, weight: 900)[#icon] ]#title]) +
      if(body != []){
        block(
          inset: 1pt, 
          width: 100%, 
          block(fill: body_background_color, width: 100%, inset: 8pt, body))
      }
    )
}


// syntax highlighting functions from skylighting:
/* Function definitions for syntax highlighting generated by skylighting: */
#let EndLine() = raw("\n")
#let Skylighting(fill: none, number: false, start: 1, sourcelines) = {
   let blocks = []
   let lnum = start - 1
   let bgcolor = rgb("#f1f3f5")
   for ln in sourcelines {
     if number {
       lnum = lnum + 1
       blocks = blocks + box(width: if start + sourcelines.len() > 999 { 30pt } else { 24pt }, text(fill: rgb("#aaaaaa"), [ #lnum ]))
     }
     blocks = blocks + ln + EndLine()
   }
   block(fill: bgcolor, width: 100%, inset: 8pt, radius: 2pt, blocks)
}
#let AlertTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let AnnotationTok(s) = text(fill: rgb("#5e5e5e"),raw(s))
#let AttributeTok(s) = text(fill: rgb("#657422"),raw(s))
#let BaseNTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let BuiltInTok(s) = text(fill: rgb("#003b4f"),raw(s))
#let CharTok(s) = text(fill: rgb("#20794d"),raw(s))
#let CommentTok(s) = text(fill: rgb("#5e5e5e"),raw(s))
#let CommentVarTok(s) = text(style: "italic",fill: rgb("#5e5e5e"),raw(s))
#let ConstantTok(s) = text(fill: rgb("#8f5902"),raw(s))
#let ControlFlowTok(s) = text(weight: "bold",fill: rgb("#003b4f"),raw(s))
#let DataTypeTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let DecValTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let DocumentationTok(s) = text(style: "italic",fill: rgb("#5e5e5e"),raw(s))
#let ErrorTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let ExtensionTok(s) = text(fill: rgb("#003b4f"),raw(s))
#let FloatTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let FunctionTok(s) = text(fill: rgb("#4758ab"),raw(s))
#let ImportTok(s) = text(fill: rgb("#00769e"),raw(s))
#let InformationTok(s) = text(fill: rgb("#5e5e5e"),raw(s))
#let KeywordTok(s) = text(weight: "bold",fill: rgb("#003b4f"),raw(s))
#let NormalTok(s) = text(fill: rgb("#003b4f"),raw(s))
#let OperatorTok(s) = text(fill: rgb("#5e5e5e"),raw(s))
#let OtherTok(s) = text(fill: rgb("#003b4f"),raw(s))
#let PreprocessorTok(s) = text(fill: rgb("#ad0000"),raw(s))
#let RegionMarkerTok(s) = text(fill: rgb("#003b4f"),raw(s))
#let SpecialCharTok(s) = text(fill: rgb("#5e5e5e"),raw(s))
#let SpecialStringTok(s) = text(fill: rgb("#20794d"),raw(s))
#let StringTok(s) = text(fill: rgb("#20794d"),raw(s))
#let VariableTok(s) = text(fill: rgb("#111111"),raw(s))
#let VerbatimStringTok(s) = text(fill: rgb("#20794d"),raw(s))
#let WarningTok(s) = text(style: "italic",fill: rgb("#5e5e5e"),raw(s))



#let article(
  title: none,
  subtitle: none,
  authors: none,
  keywords: (),
  date: none,
  abstract-title: none,
  abstract: none,
  thanks: none,
  cols: 1,
  lang: "en",
  region: "US",
  font: none,
  fontsize: 11pt,
  title-size: 1.5em,
  subtitle-size: 1.25em,
  heading-family: none,
  heading-weight: "bold",
  heading-style: "normal",
  heading-color: black,
  heading-line-height: 0.65em,
  mathfont: none,
  codefont: none,
  linestretch: 1,
  sectionnumbering: none,
  linkcolor: none,
  citecolor: none,
  filecolor: none,
  toc: false,
  toc_title: none,
  toc_depth: none,
  toc_indent: 1.5em,
  doc,
) = {
  // Set document metadata for PDF accessibility
  set document(title: title, keywords: keywords)
  set document(
    author: authors.map(author => content-to-string(author.name)).join(", ", last: " & "),
  ) if authors != none and authors != ()
  set par(
    justify: true,
    leading: linestretch * 0.65em
  )
  set text(lang: lang,
           region: region,
           size: fontsize)
  set text(font: font) if font != none
  show math.equation: set text(font: mathfont) if mathfont != none
  show raw: set text(font: codefont) if codefont != none

  set heading(numbering: sectionnumbering)

  show link: set text(fill: rgb(content-to-string(linkcolor))) if linkcolor != none
  show ref: set text(fill: rgb(content-to-string(citecolor))) if citecolor != none
  show link: this => {
    if filecolor != none and type(this.dest) == label {
      text(this, fill: rgb(content-to-string(filecolor)))
    } else {
      text(this)
    }
   }

  let has-title-block = title != none or (authors != none and authors != ()) or date != none or abstract != none
  if has-title-block {
    place(
      top,
      float: true,
      scope: "parent",
      clearance: 4mm,
      block(below: 1em, width: 100%)[

        #if title != none {
          align(center, block(inset: 2em)[
            #set par(leading: heading-line-height) if heading-line-height != none
            #set text(font: heading-family) if heading-family != none
            #set text(weight: heading-weight)
            #set text(style: heading-style) if heading-style != "normal"
            #set text(fill: heading-color) if heading-color != black

            #text(size: title-size)[#title #if thanks != none {
              footnote(thanks, numbering: "*")
              counter(footnote).update(n => n - 1)
            }]
            #(if subtitle != none {
              parbreak()
              text(size: subtitle-size)[#subtitle]
            })
          ])
        }

        #if authors != none and authors != () {
          let count = authors.len()
          let ncols = calc.min(count, 3)
          grid(
            columns: (1fr,) * ncols,
            row-gutter: 1.5em,
            ..authors.map(author =>
                align(center)[
                  #author.name \
                  #author.affiliation \
                  #author.email
                ]
            )
          )
        }

        #if date != none {
          align(center)[#block(inset: 1em)[
            #date
          ]]
        }

        #if abstract != none {
          block(inset: 2em)[
          #text(weight: "semibold")[#abstract-title] #h(1em) #abstract
          ]
        }
      ]
    )
  }

  if toc {
    let title = if toc_title == none {
      auto
    } else {
      toc_title
    }
    block(above: 0em, below: 2em)[
    #outline(
      title: toc_title,
      depth: toc_depth,
      indent: toc_indent
    );
    ]
  }

  doc
}

#set table(
  inset: 6pt,
  stroke: none
)
#let brand-color = (:)
#let brand-color-background = (:)
#let brand-logo = (:)

#set page(
  paper: "a4",
  margin: (x: 1.25in, y: 1.25in),
  numbering: "1",
  columns: 1,
)

#show: doc => article(
  title: [Номинальная негибкость цен, накопление капитала и денежная политика],
  subtitle: [Воспроизводимый анализ динамического общего равновесия с деньгами в функции полезности],
  date: [Invalid Date],
  lang: "ru",
  font: ("DejaVu Serif",),
  fontsize: 10pt,
  heading-family: ("DejaVu Serif",),
  sectionnumbering: "1.1.a",
  toc: true,
  toc_title: [Содержание],
  toc_depth: 2,
  doc,
)

= Аннотация
<аннотация>
В работе исследуется, как ограничения на пересмотр цен меняют реакции экономики на технологические и денежно-кредитные возмущения при эндогенном накоплении физического капитала. Сопоставляются два режима одной и той же экономики: гибкие цены и случайные возможности пересмотра цен по Кальво. Домохозяйство выбирает потребление, труд, инвестиции, номинальные облигации и реальные денежные остатки; последние непосредственно входят в функцию полезности. Монополистическая конкуренция, технология, предпочтения и правило центрального банка одинаковы в обоих режимах. Мы аналитически определяем стационарное состояние, выводим систему первого порядка и проверяем её независимыми численными производными и упорядоченным разложением Шура. При выбранной иллюстративной калибровке оба линейных равновесия локально определены. В ответ на положительную инновацию денежного правила выпуск при гибких ценах не меняется, а при ценах по Кальво первоначально сокращается приблизительно на 0,431 %, инвестиции --- на 2,275 %. Работа представляет воспроизводимый теоретико-численный эксперимент, а не оценку параметров по наблюдаемым данным; выводы не распространяются автоматически на нелинейное равновесие и благосостояние.

#strong[Ключевые слова:] динамическое общее равновесие; цены по Кальво; накопление капитала; деньги в полезности; рациональные ожидания; импульсные отклики; определённость равновесия.

= 1. Введение
<введение>
Центральный вопрос исследования состоит в следующем: #strong[как номинальная негибкость цен меняет равновесные реакции выпуска, потребления, инвестиций, труда и инфляции на одни и те же технологические и денежно-кредитные шоки, если физический капитал накапливается эндогенно?] Чтобы ответ не смешивал динамическую негибкость с рыночной властью, оба режима сохраняют одинаковую монополистическую конкуренцию и одну и ту же стационарную надбавку к предельным издержкам. Режим гибких цен не отождествляется с совершенно конкурентной моделью реальных деловых циклов.

Базовые составляющие модели восходят к денежной модели домохозяйства с полезностью ликвидности, модели случайного пересмотра цен Кальво (1983) и анализу линейных равновесий с рациональными ожиданиями Бланшара --- Кана (1980). Здесь не заявляется новый механизм ценообразования или эмпирическая идентификация. Цель --- представить полностью воспроизводимый численный пример с проверкой соответствия между нелинейными условиями, их линеаризацией и полученным решением. Особое внимание уделено различию между номинальной безрисковой доходностью и случайной реальной доходностью облигации.

Вклад данной версии ограничен двумя результатами. Во-первых, получен численно согласованный общий стационар при одинаковой надбавке в обоих режимах. Во-вторых, найденные решения и импульсные отклики проверены альтернативным методом упорядоченного разложения Шура и независимым вычислением производных. Эти проверки относятся к модели первого порядка около детерминированного стационара с нулевой инфляцией.

= 2. Экономическая среда и задача домохозяйства
<экономическая-среда-и-задача-домохозяйства>
Экономика закрыта. Время дискретно; период обозначен индексом (t=0,1,). Представительное домохозяйство выбирает потребление (C\_t), предложение труда (N\_t), капитал (K\_{t+1}), номинальные облигации (B\_t) и номинальные остатки (M\_t). Предпочтения имеют вид

$ E_0 sum_(t = 0)^oo beta^t [frac(C_t^(1 - sigma) - 1, 1 - sigma) - chi_n frac(N_t^(1 + phi), 1 + phi) + chi_m frac(\(M_t\/P_t\)^(1 - eta_m)- 1, 1 - eta_m)] . $

Для показателей, равных единице, соответствующий член понимается как логарифмический предел. Здесь (0\<\<1); остальные параметры предпочтений положительны. Реальные остатки (m\_t=M\_t/P\_t) дают текущие услуги ликвидности, а потребление и деньги аддитивно сепарабельны.

В периоде (t) домохозяйство покупает номинальную облигацию за (B\_t) денежных единиц, которая принесёт ((1+i\_t)B\_t) денежных единиц в следующем периоде. Его номинальное бюджетное ограничение имеет вид

$ P_t C_t + P_t K_(t + 1) + B_t + M_t =  & W_t N_t + P_t\(r_t^k + 1 - delta\)K_t\
 & +\(1 + i_(t - 1)\)B_(t - 1) + M_(t - 1) + D_t + P_t T_t . $

Здесь (r\_t^k) --- реальная арендная плата за единицу установленного капитала, () --- норма амортизации, (D\_t) --- номинальные дивиденды, (T\_t) --- чистые трансферты в единицах конечного товара. Капитал (K\_t) предопределён в начале периода, тогда как (K\_{t+1}) выбирается в периоде (t).

Определим валовую инфляцию (#emph[t=P\_t/P]{t-1}) и стохастический дисконтирующий фактор реального потребления

$ cal(M)_(t\,t + 1) = beta (C_(t + 1) / C_t)^(- sigma) . $

При внутренних решениях условия оптимальности для капитала и номинальной облигации записываются как

$ 1 = E_t #h(-1em) [cal(M)_(t\,t + 1) \( r_(t + 1)^k + 1 - delta \)]\,#h(2em) 1 = E_t #h(-1em) [cal(M)_(t\,t + 1) frac(1 + i_t, Pi_(t + 1))] . $

Облигация безрискова #strong[номинально], но при случайной инфляции её реальная доходность ((1+i\_t)/\_{t+1}) не известна в момент (t). Для труда и денег получаем

$ chi_n N_t^phi = C_t^(- sigma) w_t\,#h(2em) frac(chi_m m_t^(- eta_m), C_t^(- sigma)) = frac(i_t, 1 + i_t) . $

Условие денежного спроса показывает альтернативную стоимость хранения денег, не выплачивающих номинального процента. Аддитивная сепарабельность означает, что при процентном правиле и эндогенном предложении денег остатки (m\_t) восстанавливаются после решения реального и инфляционного блоков. Допустимость бесконечного плана требует ограничений заимствования, исключающих схемы Понци, и соответствующих трансверсальных условий; локальные численные тесты ниже сами по себе их не доказывают.

= 3. Фирмы, рыночная структура и установление цен
<фирмы-рыночная-структура-и-установление-цен>
Совершенно конкурентная фирма конечного продукта агрегирует дифференцированные товары по технологии Диксита --- Стиглица:

$ Y_t = (integral_0^1 Y_t \( j \)^(\(epsilon - 1\)\/epsilon) d j)^(epsilon\/\(epsilon - 1\))\,#h(2em) Y_t\(j\)= (frac(P_t\(j\), P_t))^(- epsilon) Y_t\, $

где (\>1). Промежуточная фирма использует капитал и труд:

$ Y_t\(j\)= A_t (K_t \( j \)^alpha) (N_t \( j \)^(1 - alpha))\,#h(2em) 0 < alpha < 1 . $

Капитал и труд свободно перераспределяются между фирмами внутри периода, поэтому цены факторов и реальные предельные издержки (mc\_t) общие. С учётом ценовой дисперсии

$ Delta_t = integral_0^1 (frac(P_t\(j\), P_t))^(- epsilon) d j $

агрегированное производство и условия спроса на факторы удовлетворяют

$ Y_t = frac(A_t K_t^alpha dot.op N_t^(1 - alpha), Delta_t)\,quad w_t =\(1 - alpha\)m c_t frac(Y_t Delta_t, N_t)\,quad r_t^k = alpha m c_t frac(Y_t Delta_t, K_t) . $

== 3.1. Гибкие цены
<гибкие-цены>
При возможности пересматривать цены в каждом периоде фирма устанавливает постоянную оптимальную надбавку (=/()). Поэтому в симметричном равновесии

$ m c_t = mu^(- 1) = frac(epsilon - 1, epsilon)\,#h(2em) Delta_t = 1 . $

Монополистическая конкуренция и связанные с ней стационарные искажения сохраняются и в этом контрольном режиме.

== 3.2. Цены по Кальво
<цены-по-кальво>
С вероятностью (1-) фирма может выбрать новую цену, а с вероятностью () обязана сохранить прежнюю. Обозначим относительную цену пересмотра (p\_t#super[\*=P\_t]\*/P\_t), а предельную полезность потребления (\_t=C\_t^{-}). Оптимальная цена определяется рекурсивной системой

$ F_t & = lambda_t m c_t Y_t + beta theta E_t\[Pi_(t + 1)^epsilon F_(t + 1)\]\,\
G_t & = lambda_t Y_t + beta theta E_t\[Pi_(t + 1)^(epsilon - 1) G_(t + 1)\]\,\
p_t^(*) & = frac(epsilon, epsilon - 1) F_t / G_t . $

Здесь множитель () уже содержится в рекурсии и не должен учитываться второй раз. Индекс цен и ценовая дисперсия подчиняются

$ 1 =\(1 - theta\)\(p_t^(*)\)^(1 - epsilon)+ theta Pi_t^(epsilon - 1)\, $

$ Delta_t =\(1 - theta\)\(p_t^(*)\)^(- epsilon)+ theta Pi_t^epsilon Delta_(t - 1) . $

Нулевой тренд инфляции и общий рынок факторов позволяют получить в первом порядке стандартную новокейнсианскую кривую Филлипса:

$ pi_t = beta E_t pi_(t + 1) + kappa_p accent(m c, ̂)_t\,#h(2em) kappa_p = frac(\(1 - theta\)\(1 - beta theta\), theta) . $

Здесь (\_t=\_t), а (\_t) --- логарифмическое отклонение реальных предельных издержек от стационара. Для первого порядка вокруг нулевой инфляции (\_t=0) при стационарной начальной дисперсии. Это не означает отсутствия издержек ценовой дисперсии во втором порядке.

= 4. Общее равновесие и денежная политика
<общее-равновесие-и-денежная-политика>
Товары используются на потребление и валовые инвестиции:

$ Y_t = C_t + I_t\,#h(2em) K_(t + 1) =\(1 - delta\)K_t + I_t . $

Рынки труда и капитала очищаются в обоих режимах цен. Номинальные облигации имеют нулевое чистое предложение, то есть в агрегате (B\_t=0); прибыль фирм возвращается домохозяйствам как дивиденды. Для согласованного бюджета консолидированных денежных властей без государственных закупок и долга реальные чистые трансферты могут финансироваться эмиссией: (P\_tT\_t=M\_t-M\_{t-1}). При процентном правиле количество денег эндогенно приспосабливается к денежному спросу.

Стационарная валовая номинальная ставка равна (1+i=1/). Правило политики в локальных координатах:

$ tilde(i)_t = phi.alt_pi pi_t + phi.alt_y hat(y)_t + v_t\,#h(2em) tilde(i)_t = log\(1 + i_t\)- log\(1 + macron(i)\). $

#strong[Важно:] реакция центрального банка определяется отклонением выпуска (y\_t) от его стационарного значения, а не разрывом относительно гибкоценового выпуска. При сопоставлении двух режимов это правило не изменяется. Экзогенные процессы имеют вид

$ hat(a)_(t + 1) = rho_a hat(a)_t + epsilon.alt_(t + 1)^a\,#h(2em) v_(t + 1) = rho_v v_t + epsilon.alt_(t + 1)^v . $

Инновации не коррелируют с доступной на момент (t) информацией. Денежный шок (v\_t) является #strong[инновацией правила], а не обязательно фактическим увеличением равновесной номинальной ставки на ту же величину.

= 5. Аналитическое стационарное состояние
<аналитическое-стационарное-состояние>
Положим (A=1), () и (). Условия Эйлера дают

$ macron(r)^k = beta^(- 1) - 1 + delta\,#h(2em) macron(i) = beta^(- 1) - 1\,#h(2em) overline(m c) = frac(epsilon - 1, epsilon) . $

Стационарные доли выводятся без численного поиска:

$ macron(K) / macron(Y) = frac(alpha overline(m c), macron(r)^k)\,quad s_I = macron(I) / macron(Y) = delta macron(K) / macron(Y)\,quad s_C = 1 - s_I . $

Для трудо-капитального отношения

$ macron(K) / macron(N) = (frac(alpha overline(m c), macron(r)^k))^(1\/\(1 - alpha\))\,#h(2em) macron(Y) / macron(N) = (macron(K) / macron(N))^alpha . $

Заработная плата равна (w=(1-),(Y/N)). Пусть (C/N=s\_C(Y/N)). Тогда

$ macron(N) = [macron(w) / chi_n (s_C macron(Y) / macron(N))^(- sigma)]^(1\/\(phi + sigma\))\,#h(2em) macron(m) = [chi_m macron(C)^sigma frac(1 + macron(i), macron(i))]^(1\/eta_m) . $

Указанные условия требуют (0\<s\_I\<1). Одинаковая стационарная надбавка обеспечивает совпадение стационарных реальных значений двух режимов. При базовой калибровке получены следующие значения:

#table(
  columns: 2,
  align: (left,right,),
  table.header([Показатель], [Значение],),
  table.hline(),
  [Реальная аренда капитала (r^k)], [0,035101],
  [Номинальная чистая ставка (i)], [0,010101],
  [Реальные предельные издержки], [0,833333],
  [Капитал к выпуску], [7,834532],
  [Инвестиции к выпуску], [0,195863],
  [Потребление к выпуску], [0,804137],
  [Труд (N)], [0,833263],
  [Выпуск (Y)], [2,296765],
  [Потребление (C)], [1,846913],
  [Капитал (K)], [17,994083],
)
= 6. Линеаризация и динамическая система
<линеаризация-и-динамическая-система>
Для положительных переменных (x\_t=\(X\_t/X)). Процентная ставка применяется только в определении (i\_t), приведённом выше. Первые производные агрегированного производства, спроса на факторы и предложения труда дают

$ hat(y)_t = hat(a)_t + alpha hat(k)_t +\(1 - alpha\)hat(n)_t\, $

$ accent(m c, ̂)_t = sigma hat(c)_t +\(phi + alpha\)hat(n)_t - hat(a)_t - alpha hat(k)_t\, $

$ hat(r)_t^k = sigma hat(c)_t +\(1 + phi\)hat(n)_t - hat(k)_t . $

Уравнения накопления капитала, облигационного и капитального выбора соответственно приводят к

$ hat(k)_(t + 1) =\(1 - delta\)hat(k)_t + delta / s_I\(hat(y)_t - s_C hat(c)_t\)\, $

$ E_t hat(c)_(t + 1) = hat(c)_t + frac(tilde(i)_t - E_t pi_(t + 1), sigma)\, $

$ sigma\(E_t hat(c)_(t + 1) - hat(c)_t\)= q E_t hat(r)_(t + 1)^k\,#h(2em) q = beta macron(r)^k . $

Спрос на деньги восстанавливается статически:

$ eta_m hat(m)_t = sigma hat(c)_t - 1 / macron(i) tilde(i)_t . $

Для цен по Кальво динамический вектор после исключения статических переменных состоит из состояний ((k\_t,a\_t,v\_t)) и переменных скачка ((c\_t,\_t,n\_t)). Хотя труд выбирается внутрипериодно, его ожидание на следующий период в редуцированной системе определяется капитальным уравнением Эйлера. При гибких ценах из (\_t=0) можно исключить труд, и остаются две переменные скачка --- потребление и инфляция.

Динамическую систему записываем как

$ vec(x_(t + 1), E_t y_(t + 1)) = sans(A) vec(x_t, y_t) + vec(sans(G), 0) epsilon.alt_(t + 1) . $

Для расчёта политики (y\_t=P x\_t) необходимо не только совпадение числа собственных значений вне единичного круга с числом переменных скачка, но и условие полного ранга соответствующего инвариантного подпространства.

= 7. Калибровка и метод численного решения
<калибровка-и-метод-численного-решения>
Ни один из параметров ниже не оценивался на наблюдаемых данных. Они выбраны для воспроизводимого иллюстративного эксперимента.

#table(
  columns: 3,
  align: (left,right,left,),
  table.header([Параметр], [Значение], [Интерпретация],),
  table.hline(),
  [\()], [0,99], [Дисконтирование],
  [\()], [0,33], [Доля капитала в технологии],
  [\()], [0,025], [Амортизация за период],
  [\()], [6], [Эластичность замещения],
  [\()], [0 или 0,75], [Вероятность сохранения цены],
  [\(,)], [1; 1], [Кривизна потребления и труда],
  [\(\_n,\_m,\_m)], [1; 1; 1], [Труд и ликвидность],
  [\(\_,\_y)], [1,5; 0,125], [Реакция денежной политики],
  [\(\_a,\_v)], [0,9; 0,8], [Устойчивость шоков],
)
После аналитического вычисления стационара независимая численная дифференциация исходных нелинейных условий даёт коэффициенты линеаризованной системы. Затем найденное исходное решение на собственных векторах сравнивается с решением, построенным методом упорядоченного обобщённого разложения Шура (QZ). Отдельно проверяются число нестабильных корней, ранг, инвариантность подпространства и остатки уравнений. Таким образом, совпадение нескольких численных путей является тестом корректности #strong[линейного решения], а не доказательством глобальной определённости.

= 8. Численная определённость и независимая проверка
<численная-определённость-и-независимая-проверка>
В обоих режимах максимальный абсолютный остаток проверенных нелинейных условий в стационаре составляет (1{,}11^{-16}). Сравнение матриц, полученных аналитической реализацией и независимыми центральными разностями, даёт следующие результаты:

#table(
  columns: (33.33%, 33.33%, 33.33%),
  align: (left,right,right,),
  table.header([Диагностика], [Гибкие цены], [Цены по Кальво],),
  table.hline(),
  [Максимальное расхождение матриц], [\(5{,}00^{-11})], [\(9{,}14^{-10})],
  [Нестабильные корни], [2], [3],
  [Независимые переменные скачка], [2], [3],
  [Минимальное сингулярное число блока ранга], [0,5664], [0,3264],
  [Согласованность QZ и метода собственных векторов], [Да], [Да],
)
Для гибких цен собственные значения составляют (0{,}800000), (0{,}900000), (0{,}951375), (1{,}072633), (1{,}500000). Для цен по Кальво значения равны (0{,}800000), (0{,}900000), (0{,}945482), (1{,}068381), (1{,}663903), (2{,}243578). Таким образом, три состояния соответствуют трём корням внутри единичного круга, а число нестабильных корней совпадает с числом переменных скачка в каждом режиме. Условия ранга также выполняются.

Наклон кривой Филлипса при (75) равен (\_p=0{,}0858333). Независимая дифференциация точных рекурсий пересмотра цен подтверждает этот коэффициент для выбранных предпосылок. Программа автоматической проверки завершает 19 тестов без ошибок. Максимальное различие рассчитанных двумя методами импульсных откликов за 41 период ниже (7^{-11}) логарифмической единицы.

= 9. Импульсные отклики
<импульсные-отклики>
Положительная технологическая инновация задаётся как (^a\_0=0{,}01) логарифмической единицы (примерно 1 %). Положительная инновация денежного правила задаётся как (^v\_0=0{,}0025) логарифмической единицы валовой номинальной ставки. Траектории рассчитываются на горизонте от нулевого до сорокового периода. Все показатели в таблице ниже --- первоначальные отклонения, умноженные на 100, то есть приблизительные процентные изменения или процентные пункты для инфляции.

#table(
  columns: (20%, 20%, 20%, 20%, 20%),
  align: (left,right,right,right,right,),
  table.header([Переменная, период 0], [Технология: гибкие], [Технология: Кальво], [Денежный шок: гибкие], [Денежный шок: Кальво],),
  table.hline(),
  [Выпуск], [+1,337], [+1,250], [0,000], [−0,431],
  [Потребление], [+0,331], [+0,349], [0,000], [+0,018],
  [Инвестиции], [+5,470], [+4,948], [0,000], [−2,275],
  [Труд], [+0,503], [+0,373], [0,000], [−0,644],
  [Инфляция], [−0,238], [−0,229], [−0,357], [−0,320],
)
== 9.1. Технологическое возмущение
<технологическое-возмущение>
При гибких ценах первоначальный рост выпуска составляет приблизительно 1,337 %, а при Кальво --- 1,250 %. Рост инвестиций достигает соответственно 5,470 % и 4,948 %. В обоих режимах распространение технологического шока происходит через доходность установленного капитала и оптимальные планы накопления; ценовая негибкость меняет количественную реакцию и динамику инфляции.

#figure([
#box(image("figures/technology_vypusk.svg", width: 88.0%))
], caption: figure.caption(
position: bottom, 
[
Реакция выпуска на положительный технологический шок при двух режимах установления цен.
]), 
kind: "quarto-float-fig", 
supplement: "Рисунок", 
)
<fig-technology-output>


== 9.2. Денежно-кредитное возмущение
<денежно-кредитное-возмущение>
При гибких ценах и аддитивно-сепарабельной полезности денег положительная инновация денежного правила не меняет реальные решения. При Кальво первоначальные выпуск и труд сокращаются на 0,431 % и 0,644 %, а инвестиции --- на 2,275 %. Таким образом, основная часть первоначального изменения реальных расходов при выбранной калибровке приходится на инвестиции.

#figure([
#box(image("figures/monetary_vypusk.svg", width: 88.0%))
], caption: figure.caption(
position: bottom, 
[
Реакция выпуска на положительную инновацию денежного правила.
]), 
kind: "quarto-float-fig", 
supplement: "Рисунок", 
)
<fig-monetary-output>


#figure([
#box(image("figures/monetary_investicii.svg", width: 88.0%))
], caption: figure.caption(
position: bottom, 
[
Реакция валовых инвестиций на положительную инновацию денежного правила.
]), 
kind: "quarto-float-fig", 
supplement: "Рисунок", 
)
<fig-monetary-investment>


Первоначальное потребление при Кальво #strong[немного увеличивается] (примерно на 0,018 %). Этот знак нельзя скрывать или заменять стандартной интуицией простой трёхуравневой модели: в данной постановке инвестиции могут меняться без издержек корректировки, а ресурсное ограничение требует согласованного распределения выпуска между потреблением и накоплением капитала. Это результат конкретной калибровки, а не общий закон денежной трансмиссии.

#figure([
#box(image("figures/monetary_potreblenie.svg", width: 88.0%))
], caption: figure.caption(
position: bottom, 
[
Реакция потребления на положительную инновацию денежного правила.
]), 
kind: "quarto-float-fig", 
supplement: "Рисунок", 
)
<fig-monetary-consumption>


Положительный шок (v\_t) не тождествен увеличению #strong[реализованной] номинальной ставки на ту же величину: эндогенное изменение выпуска и инфляции входит в правило центрального банка. Интерпретация знаков требует учитывать все члены этого правила.

= 10. Границы результатов и интерпретация
<границы-результатов-и-интерпретация>
Полученная разница между режимами характеризует локальную динамику конкретной экономики при заданной калибровке, а не причинный эффект, оценённый на реальных данных. В частности, в данной версии отсутствуют издержки корректировки инвестиций, фирменно-специфический капитал и политика, ориентированная непосредственно на гибкоценовой разрыв выпуска. Предполагается, что факторы производства свободно перемещаются между фирмами, поэтому стандартный коэффициент наклона Кальво неприменим к моделям с фирменно-специфическими капитальными запасами без дополнительного вывода.

Во втором порядке ценовая дисперсия создаёт потери ресурсов, а стохастические ковариации доходностей становятся существенными для риск-премий и благосостояния. В настоящем расчёте они #strong[не] оцениваются. Ограничения заимствования и трансверсальные условия не были независимо доказаны для полной бесконечномерной стохастической задачи. Следовательно, результаты не следует называть решением полной нелинейной экономики.

Наконец, численная определённость подтверждена для #strong[одного] набора параметров. Условие вида (\_\>1), хотя и выполнено здесь, само по себе не доказывает единственность для произвольной модели с капиталом. Статус результатов ограничивается проверенными собственными значениями и рангом соответствующего численного оператора.

= 11. Заключение
<заключение>
Сравнение двух режимов ценообразования в экономике с капиталом, номинальными облигациями и полезностью денег показывает, что номинальная негибкость меняет передачу денежного шока в реальные переменные. При фиксированных предпочтениях, технологии, наценке и правиле политики гибкие цены обеспечивают нейтральность денежной инновации для реальных величин; при Кальво та же инновация приводит к первоначальному сокращению выпуска и особенно инвестиций. Независимые проверки производных, решений на инвариантном подпространстве и условий Бланшара --- Кана подтверждают внутреннюю согласованность вычислительного эксперимента первого порядка.

Этот вывод следует интерпретировать как #strong[воспроизводимый эталонный численный результат], пригодный для дальнейшего расширения, но не как новую эмпирическую оценку или результат анализа благосостояния. Следующая исследовательская задача --- отдельно исследовать устойчивость эффекта к изменению калибровки и к издержкам корректировки капитала; такие упражнения не включены в приведённые оценки.

= Приложение. Протокол воспроизводимости
<приложение.-протокол-воспроизводимости>
Исходные уравнения, код решения и проверки сохранены вместе с настоящим текстом. Для пересчёта используются Python, NumPy, SciPy и Matplotlib. Проверки запускаются последовательно:

#Skylighting(([#NormalTok("python -m pip install -r requirements.txt");],
[#NormalTok("python -m unittest discover -s tests -v");],
[#NormalTok("python -m src.audit");],
[#NormalTok("python -m src.experiment");],));
Четыре таблицы импульсных откликов содержатся в каталоге results; диагностические таблицы стационара, Якобианов и собственных корней --- там же. Отдельные векторные изображения находятся в каталоге figures. Исходный текст статьи хранится в файле paper.qmd и преобразуется в PDF командой:

#Skylighting(([#NormalTok("quarto render paper.qmd --to typst");],));
Публикуемый PDF генерируется из этого файла внутри GitHub Actions. Внешний численный ввод в ходе сборки документа не выполняется: графики и таблицы основаны на проверенных результатах модели. Полный путь вычислений и исходные значения параметров включены в репозиторий.

= Литература
<литература>
+ Кальво, Г. А. (1983). «Staggered Prices in a Utility-Maximizing Framework». #emph[Journal of Monetary Economics], 12(3), 383--398. DOI: 10.1016/0304-3932(83)90060-0.
+ Бланшар, О. Ж., Кан, Ч. М. (1980). «The Solution of Linear Difference Models under Rational Expectations». #emph[Econometrica], 48(5), 1305--1311. DOI: 10.2307/1912186.
+ Симс, К. А. (2002). «Solving Linear Rational Expectations Models». #emph[Computational Economics], 20(1--2), 1--20.
+ Гали, Ж. (2015). #emph[Monetary Policy, Inflation, and the Business Cycle: An Introduction to the New Keynesian Framework]. Второе издание. Princeton University Press.
+ Вудфорд, М. (2003). #emph[Interest and Prices: Foundations of a Theory of Monetary Policy]. Princeton University Press.
