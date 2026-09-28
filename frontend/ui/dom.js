/**
 * Build DOM from developer-owned template literals. Substitutions never enter
 * the HTML parser: text becomes textContent and attributes are assigned later.
 * @param {TemplateStringsArray} strings
 * @param {...unknown} values
 * @returns {DocumentFragment}
 */
export function html(strings, ...values) {
  const marker = /__freight_slot_(\d+)__/g;
  const source = strings.reduce(
    (result, part, index) => result + (index ? `__freight_slot_${index - 1}__` : "") + part,
    "",
  );
  const parsed = new DOMParser().parseFromString(source, "text/html");
  const fragment = document.createDocumentFragment();
  fragment.append(...parsed.body.childNodes);
  const walker = document.createTreeWalker(
    fragment,
    NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
  );
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (node instanceof Element) bindAttributes(node, values, marker);
    else bindText(/** @type {Text} */ (node), values, marker);
  }
  return fragment;
}

/** Replace text slots with nodes or literal text, including nested lists. */
function bindText(node, values, marker) {
  const parts = node.textContent.split(marker);
  if (parts.length === 1) return;
  const replacement = document.createDocumentFragment();
  parts.forEach((part, index) => appendValue(replacement, index % 2 ? values[Number(part)] : part));
  node.replaceWith(replacement);
}

/** Append a display value without interpreting its text as markup. */
function appendValue(parent, value) {
  if (Array.isArray(value)) value.forEach((item) => appendValue(parent, item));
  else if (value instanceof Node) parent.append(value);
  else if (value !== null && value !== undefined && value !== false) {
    const text = document.createTextNode("");
    text.textContent = String(value);
    parent.append(text);
  }
}

/** Bind attributes after parsing; boolean attributes retain boolean semantics. */
function bindAttributes(element, values, marker) {
  for (const attribute of [...element.attributes]) {
    if (attribute.name.startsWith("on") || attribute.name === "srcdoc") {
      throw new Error("Executable DOM attributes are forbidden");
    }
    const value = attribute.value.replace(marker, (_, index) =>
      String(values[Number(index)] ?? ""),
    );
    if (["href", "src", "action"].includes(attribute.name) && !/^(https?:|\/|#)/i.test(value)) {
      throw new Error("Unsupported link protocol");
    }
    if (["disabled", "selected", "checked", "hidden", "open"].includes(attribute.name)) {
      const slot = /^__freight_slot_(\d+)__$/.exec(attribute.value);
      element.toggleAttribute(attribute.name, slot ? Boolean(values[Number(slot[1])]) : true);
    } else element.setAttribute(attribute.name, value);
  }
}

/** Find a required HTML element and fail clearly when a view contract breaks.
 * @template {HTMLElement} [T=HTMLElement]
 * @param {string} selector
 * @param {ParentNode} [root=document]
 * @returns {T}
 */
export function requiredElement(selector, root = document) {
  const element = root.querySelector(selector);
  if (!(element instanceof HTMLElement)) throw new Error(`Missing element: ${selector}`);
  return /** @type {T} */ (element);
}
