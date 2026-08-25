use serde::{Deserialize, Serialize};
use crate::classification::matcher::CompiledRuleMatcher;
use crate::classification::scoring::{calculate_confidence, ScoreBreakdown};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuleDefinition {
    pub id: String,
    pub nome: String,
    pub categoria: String,
    pub subcategoria: Option<String>,
    pub entidade: Option<String>,
    pub caminho_fisico: String,
    pub origem: String,
    pub categoria_key: Option<String>,
    pub palavras_chave: Vec<String>,
    pub regex: Vec<String>,
    pub extensoes: Vec<String>,
    pub confianca_base: f64,
    pub usar_para_automacao: bool,
    pub idioma: Option<String>,
    pub sinonimos: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClassificationCandidate {
    pub tag_id: String,
    pub nome: String,
    pub categoria: String,
    pub subcategoria: Option<String>,
    pub entidade: Option<String>,
    pub caminho_fisico: String,
    pub origem: String,
    pub confianca: f64,
    pub scores: ScoreBreakdown,
    pub is_user_rule: bool,
    pub rule_index: usize,
}

pub struct ClassificationKernel {
    matchers: Vec<CompiledRuleMatcher>,
    definitions: Vec<RuleDefinition>,
}

impl ClassificationKernel {
    pub fn new(rules: Vec<RuleDefinition>) -> Self {
        let mut matchers = Vec::with_capacity(rules.len());
        for rule in &rules {
            let is_user = rule.origem == "user";
            let mut all_keywords = rule.palavras_chave.clone();
            for sin in &rule.sinonimos {
                if !all_keywords.contains(sin) {
                    all_keywords.push(sin.clone());
                }
            }

            let matcher = CompiledRuleMatcher::new(
                rule.id.clone(),
                &all_keywords,
                &rule.regex,
                &rule.extensoes,
                rule.confianca_base,
                is_user,
            );
            matchers.push(matcher);
        }

        Self {
            matchers,
            definitions: rules,
        }
    }

    pub fn classify(
        &self,
        text: &str,
        file_ext: &str,
        score_origem: f64,
    ) -> Option<ClassificationCandidate> {
        let text_lower = text.to_lowercase();
        let mut candidates = Vec::new();

        for (idx, matcher) in self.matchers.iter().enumerate() {
            let (score_conteudo, score_tipo) = matcher.evaluate(&text_lower, text, file_ext);
            let (confianca, scores) = calculate_confidence(
                score_conteudo,
                score_tipo,
                score_origem,
                matcher.confianca_base,
            );

            if confianca >= 0.20 {
                let def = &self.definitions[idx];
                candidates.push(ClassificationCandidate {
                    tag_id: def.id.clone(),
                    nome: def.nome.clone(),
                    categoria: def.categoria.clone(),
                    subcategoria: def.subcategoria.clone(),
                    entidade: def.entidade.clone(),
                    caminho_fisico: def.caminho_fisico.clone(),
                    origem: def.origem.clone(),
                    confianca,
                    scores,
                    is_user_rule: matcher.is_user_rule,
                    rule_index: idx,
                });
            }
        }

        if candidates.is_empty() {
            return None;
        }

        // Sort by precedence:
        // 1. User rule (true > false)
        // 2. Higher confidence (descending)
        // 3. Definition order (ascending rule_index)
        candidates.sort_by(|a, b| {
            b.is_user_rule.cmp(&a.is_user_rule)
                .then_with(|| b.confianca.partial_cmp(&a.confianca).unwrap_or(std::cmp::Ordering::Equal))
                .then_with(|| a.rule_index.cmp(&b.rule_index))
        });

        Some(candidates[0].clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_classify_boleto_and_energy() {
        let rule_boleto = RuleDefinition {
            id: "sys_boleto".into(),
            nome: "Boleto".into(),
            categoria: "Faturas".into(),
            subcategoria: Some("Boleto".into()),
            entidade: Some("Banco".into()),
            caminho_fisico: "Faturas/Boletos".into(),
            origem: "system".into(),
            categoria_key: None,
            palavras_chave: vec!["vencimento".into(), "pagavel em qualquer banco".into()],
            regex: vec![r"\b\d{44}\b".into()],
            extensoes: vec![".pdf".into()],
            confianca_base: 0.98,
            usar_para_automacao: true,
            idioma: Some("ptBR".into()),
            sinonimos: vec![],
        };

        let rule_energy = RuleDefinition {
            id: "sys_energy".into(),
            nome: "Energia Elétrica".into(),
            categoria: "Faturas".into(),
            subcategoria: Some("Luz".into()),
            entidade: Some("AES Sul".into()),
            caminho_fisico: "Faturas/Luz".into(),
            origem: "system".into(),
            categoria_key: None,
            palavras_chave: vec!["aes sul".into(), "energia eletrica".into(), "kwh".into(), "vencimento".into()],
            regex: vec![r"\baes\s+sul\b".into()],
            extensoes: vec![".pdf".into()],
            confianca_base: 0.95,
            usar_para_automacao: true,
            idioma: Some("ptBR".into()),
            sinonimos: vec![],
        };

        let kernel = ClassificationKernel::new(vec![rule_boleto, rule_energy]);

        // Test boleto with 44 digits
        let text_boleto = "Comprovante de pagamento Banco do Brasil 23793381286008301352856000063307789012345678 Vencimento 10/08/2026";
        let res_boleto = kernel.classify(text_boleto, ".pdf", 0.0).unwrap();
        assert_eq!(res_boleto.tag_id, "sys_boleto");
        assert!(res_boleto.confianca >= 0.85);

        // Test energy bill
        let text_energy = "AES Sul Distribuidora de Energia S.A. Consumo ativo 350 kWh Vencimento 15/08/2026";
        let res_energy = kernel.classify(text_energy, ".pdf", 0.0).unwrap();
        assert_eq!(res_energy.tag_id, "sys_energy");
        assert!(res_energy.confianca >= 0.85);
    }
}
