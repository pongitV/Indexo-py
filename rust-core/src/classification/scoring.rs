use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScoreBreakdown {
    pub conteudo: f64,
    pub tipo: f64,
    pub origem: f64,
}

pub fn calculate_confidence(
    score_conteudo: f64,
    score_tipo: f64,
    score_origem: f64,
    confianca_base: f64,
) -> (f64, ScoreBreakdown) {
    let weighted_conteudo = (score_conteudo * confianca_base).clamp(0.0, 1.0);
    let weighted_tipo = score_tipo.clamp(0.0, 1.0);
    let weighted_origem = score_origem.clamp(0.0, 1.0);

    let confianca = 0.70 * weighted_conteudo + 0.20 * weighted_tipo + 0.10 * weighted_origem;
    let rounded_conf = (confianca * 1000.0).round() / 1000.0;

    let breakdown = ScoreBreakdown {
        conteudo: (weighted_conteudo * 100.0).round() / 100.0,
        tipo: (weighted_tipo * 100.0).round() / 100.0,
        origem: (weighted_origem * 100.0).round() / 100.0,
    };

    (rounded_conf, breakdown)
}
