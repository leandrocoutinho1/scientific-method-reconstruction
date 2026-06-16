# Registro do Pipeline

Este documento registra a evolução metodológica do protótipo de reconstrução automática de partes faltantes em seções de metodologia científica.

O objetivo deste arquivo não é substituir o `README.md`. O `README.md` deve explicar como instalar e executar o projeto. Este documento deve funcionar como histórico de decisões, mudanças de rumo, justificativas técnicas e observações que poderão apoiar a escrita do TCC.

## Objetivo do Protótipo

O projeto busca testar a viabilidade de reconstruir trechos ausentes de metodologias científicas usando:

- extração estrutural de artigos com GROBID;
- identificação automática de seções metodológicas;
- criação artificial de lacunas;
- reconstrução do trecho ausente com modelo de linguagem;
- comparação posterior entre trecho original e trecho reconstruído.

## Estado Atual do Pipeline

O fluxo atual está organizado em quatro scripts numerados:

```text
src/1_parse_with_grobid.py
src/2_extract_method_sections.py
src/3_create_gaps.py
src/4_reconstruct_with_groq.py
```

A numeração foi adotada para deixar explícita a ordem de execução das etapas.

## Etapa 1 — Processamento com GROBID

Decisão atual:

Usar GROBID como ferramenta inicial para converter PDFs científicos em uma estrutura manipulável pelo projeto.

Entrada:

```text
data/raw_pdfs/
```

Saída:

```text
data/grobid_output/
```

Justificativa:

O GROBID já oferece extração estrutural de artigos científicos, incluindo título, corpo do texto, seções e metadados. Isso reduz a necessidade de implementar um parser próprio de PDF nesta fase inicial.

Observação:

O GROBID precisa estar rodando localmente antes da execução do script.

## Etapa 2 — Extração de Metodologias

Decisão atual:

Identificar seções metodológicas a partir dos títulos de seção extraídos pelo GROBID.

Arquivo de padrões:

```text
config/section_patterns.json
```

Entrada:

```text
data/grobid_output/
```

Saída:

```text
data/methods_extracted/
```

Justificativa:

Artigos podem nomear a metodologia de formas diferentes, como "Metodologia", "Métodos", "Materiais e Métodos", "Methods", "Experimental Setup" e outras variações. Por isso, os padrões foram externalizados em um arquivo de configuração.

Limitação conhecida:

A extração ainda depende bastante da forma como o GROBID identifica os títulos das seções. Quando o GROBID não reconhece corretamente uma seção metodológica, o script pode gerar uma extração vazia.

Decisão de momento:

Aprimorar essa etapa foi considerado importante, mas optamos por seguir primeiro para a reconstrução com LLM para validar o fluxo completo.

## Etapa 3 — Criação de Lacunas Artificiais

Decisão atual:

Remover propositalmente um parágrafo da metodologia extraída e substituir esse trecho por:

```text
[MISSING_TEXT]
```

Entrada:

```text
data/methods_extracted/
```

Saída:

```text
data/gaps/
```

Formato atual do arquivo de lacuna:

```json
{
  "gap_id": "...",
  "title": "...",
  "masked_text": "... [MISSING_TEXT] ...",
  "removed_excerpt": "...",
  "removed_section": "..."
}
```

Justificativa:

A remoção artificial permite conhecer o trecho original removido. Isso cria uma referência para comparação futura com a reconstrução gerada pelo modelo de linguagem.

Mudança de rumo registrada:

Inicialmente, os arquivos de lacuna continham muitos metadados, como contagem de palavras, posição do trecho, contexto anterior e posterior separados e outros detalhes. Para a fase atual, esses campos foram removidos para reduzir ruído e facilitar testes simples.

## Etapa 4 — Reconstrução com Groq

Decisão atual:

Usar a API da Groq para testar uma reconstrução simples com modelo de linguagem.

Entrada:

```text
data/gaps/
```

Saída:

```text
results/reconstructions/
```

Formato atual do arquivo de reconstrução:

```json
{
  "gap_id": "...",
  "title": "...",
  "removed_excerpt": "...",
  "model": "...",
  "reconstructed_excerpt": "..."
}
```

Justificativa:

A Groq foi escolhida nesta fase por permitir testar modelos de linguagem de forma simples e acessível. O objetivo atual não é comparar modelos, mas validar o fluxo de reconstrução.

Mudança de rumo registrada:

A primeira versão da reconstrução incluía campos como `confidence`, `notes` e `valid_json_response`. Esses campos foram removidos porque, neste momento, o objetivo é apenas testar a forma básica de reconstrução e comparar o trecho original com o trecho gerado.

## Decisões de Organização do Código

Os scripts executáveis do pipeline foram numerados para facilitar a ordem de uso:

```text
1_parse_with_grobid.py
2_extract_method_sections.py
3_create_gaps.py
4_reconstruct_with_groq.py
```

Os arquivos auxiliares permaneceram sem numeração:

```text
text_cleaning.py
utils.py
```

Justificativa:

A numeração ajuda a entender a sequência experimental. Os arquivos auxiliares não representam etapas executáveis do pipeline e, por isso, foram mantidos sem prefixo numérico.

## Próximos Pontos a Registrar

Este documento deve ser atualizado sempre que houver mudança relevante no rumo do projeto, por exemplo:

- alteração na estratégia de extração das metodologias;
- troca ou comparação de modelos de linguagem;
- inclusão de etapa de avaliação automática;
- inclusão de avaliação qualitativa;
- mudança no formato dos arquivos intermediários;
- problemas encontrados durante testes com PDFs reais;
- decisões tomadas para simplificar ou expandir o escopo.
