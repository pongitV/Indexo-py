use aho_corasick::{AhoCorasick, AhoCorasickBuilder, MatchKind};
use regex::Regex;
use std::collections::HashSet;

pub fn levenshtein(a: &str, b: &str) -> usize {
    let a_chars: Vec<char> = a.chars().collect();
    let b_chars: Vec<char> = b.chars().collect();
    let m = a_chars.len();
    let n = b_chars.len();
    if m == 0 {
        return n;
    }
    if n == 0 {
        return m;
    }

    let mut prev: Vec<usize> = (0..=n).collect();
    let mut curr: Vec<usize> = vec![0; n + 1];

    for i in 1..=m {
        curr[0] = i;
        for j in 1..=n {
            let cost = if a_chars[i - 1] == b_chars[j - 1] { 0 } else { 1 };
            curr[j] = (prev[j] + 1)
                .min(curr[j - 1] + 1)
                .min(prev[j - 1] + cost);
        }
        prev.copy_from_slice(&curr);
    }
    prev[n]
}

pub struct CompiledRuleMatcher {
    pub tag_id: String,
    pub keywords_raw: Vec<String>,
    pub keywords_ac: Option<AhoCorasick>,
    pub total_keywords: usize,
    pub compiled_regexes: Vec<Regex>,
    pub expected_extensions: Vec<String>,
    pub confianca_base: f64,
    pub is_user_rule: bool,
}

impl CompiledRuleMatcher {
    pub fn new(
        tag_id: String,
        keywords: &[String],
        regex_patterns: &[String],
        extensions: &[String],
        confianca_base: f64,
        is_user_rule: bool,
    ) -> Self {
        let clean_keywords: Vec<String> = keywords
            .iter()
            .map(|k| k.trim().to_lowercase())
            .filter(|k| !k.is_empty())
            .collect();

        let total_keywords = clean_keywords.len();

        let keywords_ac = if !clean_keywords.is_empty() {
            AhoCorasickBuilder::new()
                .ascii_case_insensitive(true)
                .match_kind(MatchKind::Standard)
                .build(&clean_keywords)
                .ok()
        } else {
            None
        };

        let mut compiled_regexes = Vec::new();
        for pat in regex_patterns {
            if let Ok(re) = Regex::new(pat) {
                compiled_regexes.push(re);
            }
        }

        let clean_exts: Vec<String> = extensions
            .iter()
            .map(|e| {
                let lower = e.trim().to_lowercase();
                if lower.starts_with('.') {
                    lower
                } else {
                    format!(".{}", lower)
                }
            })
            .collect();

        Self {
            tag_id,
            keywords_raw: clean_keywords,
            keywords_ac,
            total_keywords,
            compiled_regexes,
            expected_extensions: clean_exts,
            confianca_base,
            is_user_rule,
        }
    }

    pub fn evaluate(
        &self,
        text_lowercase: &str,
        raw_text: &str,
        file_ext: &str,
    ) -> (f64, f64) {
        // 1. Content score
        let mut regex_matched = false;
        for re in &self.compiled_regexes {
            if re.is_match(raw_text) || re.is_match(text_lowercase) {
                regex_matched = true;
                break;
            }
        }

        let score_conteudo = if regex_matched {
            1.0
        } else if self.total_keywords > 0 {
            let mut matched_indices = HashSet::new();
            if let Some(ref ac) = self.keywords_ac {
                for m in ac.find_iter(text_lowercase) {
                    matched_indices.insert(m.pattern().as_usize());
                }
            }

            // Fuzzy fallback for unmatched long keywords (length >= 5) to tolerate OCR errors
            if matched_indices.len() < self.total_keywords {
                let words: Vec<&str> = text_lowercase
                    .split(|c: char| !c.is_alphanumeric())
                    .filter(|w| w.len() >= 4)
                    .take(1500)
                    .collect();

                for (idx, kw) in self.keywords_raw.iter().enumerate() {
                    if matched_indices.contains(&idx) {
                        continue;
                    }
                    let kw_len = kw.len();
                    if kw_len >= 5 && !kw.contains(' ') {
                        let max_dist = if kw_len >= 8 { 2 } else { 1 };
                        for w in &words {
                            if (w.len() as isize - kw_len as isize).abs() <= max_dist as isize {
                                if levenshtein(kw, w) <= max_dist {
                                    matched_indices.insert(idx);
                                    break;
                                }
                            }
                        }
                    }
                }
            }

            (matched_indices.len() as f64) / (self.total_keywords as f64)
        } else {
            0.0
        };

        // 2. Type score
        let norm_ext = if file_ext.starts_with('.') {
            file_ext.to_lowercase()
        } else {
            format!(".{}", file_ext.to_lowercase())
        };

        let score_tipo = if self.expected_extensions.is_empty() {
            0.8
        } else if self.expected_extensions.contains(&norm_ext) {
            1.0
        } else {
            0.4
        };

        (score_conteudo, score_tipo)
    }
}
