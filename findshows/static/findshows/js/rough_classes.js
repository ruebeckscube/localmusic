// Render all rough-* classes

// Set up variables common to all functions (p is padding, d dimensions)
function setup_svg(svg, p) {
  let rough_svg = rough.svg(svg);
  const d = svg.getBoundingClientRect();
  svg.setAttribute('viewBox', '0 0 ' + (d.width + 2*p) + ' ' + (d.height + 2*p));
  return [rough_svg, d]
}

////////////////////////////////////
// All individual shape functions //
////////////////////////////////////
function rough_rect_helper(svg, p, options) {
  let [rough_svg, d] = setup_svg(svg, p)
  svg.appendChild(rough_svg.rectangle(p, p, d.width, d.height, options));
}

function rough_bg_rect(svg) {
  rough_rect_helper(svg, 10, {
    roughness: 10,
    bowing: 0,
    fill: "var(--color-sub-background)",
    fillStyle: 'solid',
  });
}

function rough_bg_musicbrainz_card(svg) {
  rough_rect_helper(svg, 2, {
    roughness: 2,
    bowing: 0,
    fill: "var(--color-highlight-item-light)",
    fillStyle: 'solid',
  });
}


// Dict that maps class names to shape functions
const rough_cls_2_fnc = {
  'rough-bg-rect': rough_bg_rect,
  'rough-bg-musicbrainz-card': rough_bg_musicbrainz_card,
}

// Process a node
function add_rough_to_node(el) {
  for (const cls in rough_cls_2_fnc) {
    for (svg of el.getElementsByClassName(cls)) {
      rough_cls_2_fnc[cls](svg);
    }
  }

}

// Set up listener; fires for initial page load on body, as well as any new
// element that htmx inserts. Any given element will be checked once and only
// once for each class name.
htmx.onLoad(function(elt) {
  add_rough_to_node(elt)
});
