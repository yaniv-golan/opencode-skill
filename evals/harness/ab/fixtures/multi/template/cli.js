import { to_title_case, count_words, truncate_text } from "./src/strings.js";
import { unique_values, chunk_array, flatten_deep } from "./src/arrays.js";
import { pick_keys, omit_keys, deep_clone } from "./src/objects.js";
import { clamp_value, round_to, sum_all } from "./src/numbers.js";

const text = "the quick brown fox";
console.log(to_title_case(text), count_words(text), truncate_text(text, 10));
console.log(JSON.stringify(unique_values([1, 1, 2])), JSON.stringify(chunk_array([1, 2, 3], 2)),
  JSON.stringify(flatten_deep([1, [2, [3]]])));
const o = { a: 1, b: { c: 2 } };
console.log(JSON.stringify(pick_keys(o, ["a"])), JSON.stringify(omit_keys(o, ["a"])), JSON.stringify(deep_clone(o)));
console.log(clamp_value(15, 0, 10), round_to(3.14159, 2), sum_all([1, 2, 3]));
