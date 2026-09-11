# Registro do Pipeline

Este documento registra a evolução metodológica do protótipo de reconstrução automática de partes faltantes em seções de metodologia científica.

O objetivo deste arquivo não é substituir o `README.md`. O `README.md` explica como instalar e executar o projeto. Este documento funciona como histórico de decisões, mudanças de rumo, justificativas técnicas e observações que poderão apoiar a escrita do TCC.

## Objetivo do Protótipo

O projeto busca testar a viabilidade de reconstruir trechos ausentes de metodologias científicas usando:

- extração de texto de artigos científicos;
- identificação automática de seções metodológicas;
- criação artificial de lacunas;
- reconstrução do trecho ausente com modelo de linguagem;
- comparação posterior entre trecho original e trecho reconstruído.

## Estado Atual

Na versão atual, o fluxo principal usa GROBID para extrair texto estruturado dos PDFs, padrões configuráveis para identificar seções metodológicas e Gemini apenas para reconstruir os trechos ausentes.

Scripts atuais:

```text
src/1_parse_with_grobid.py
src/2_extract_method_sections.py
src/3_create_gaps.py
src/4_reconstruct_with_gemini.py
```

Fluxo atual:

```text
data/raw_pdfs/
  -> data/grobid_output/
  -> data/methods_extracted/      (padrões de títulos de seção)
  -> data/gaps/
  -> results/reconstructions/     (reconstrução com Gemini)
```

## Linha do Tempo das Decisões

### Versão 1 — Pipeline Inicial com GROBID

Decisão inicial:

Usar GROBID para processar os PDFs científicos e extrair uma representação estruturada dos artigos.

Motivação:

O GROBID é uma ferramenta especializada em documentos científicos. A expectativa inicial era aproveitar sua capacidade de identificar metadados, corpo do texto, seções e referências, evitando a criação de um parser próprio de PDF.

Fluxo da versão:

```text
data/raw_pdfs/
  -> data/grobid_output/
  -> data/methods_extracted/
```

Script usado na época:

```text
src/1_parse_with_grobid.py
```

Pontos positivos observados:

- oferecia uma estrutura JSON com campos como `biblio`, `body_text`, `head_section` e `text`;
- permitia que a etapa de extração de metodologia trabalhasse sobre seções já identificadas;
- era coerente com a proposta inicial do TCC, que previa uso de ferramentas de extração estrutural de artigos.

Limitações observadas:

- exigia um serviço externo rodando via Docker;
- o fluxo não era tão intuitivo para inspeção rápida;
- algumas extrações não foram assertivas para os PDFs testados;
- em um dos testes, um artigo ficou com `0` parágrafos metodológicos extraídos.

Decisão tomada:

Manter o GROBID como primeira abordagem documentada, mas investigar uma alternativa mais simples para testar o fluxo completo.

### Versão 2 — Extração de Metodologias por Padrões de Seção

Decisão:

Criar uma etapa própria para identificar metodologias a partir dos nomes das seções extraídas.

Arquivo de padrões:

```text
config/section_patterns.json
```

Motivação:

Artigos podem nomear a metodologia de formas diferentes, como:

- `Metodologia`;
- `Métodos`;
- `Materiais e Métodos`;
- `Procedimentos Metodológicos`;
- `Methods`;
- `Methodology`;
- `Experimental Setup`.

Por isso, os padrões foram externalizados para facilitar ajustes sem alterar diretamente o código.

Script:

```text
src/2_extract_method_sections.py
```

Formato esperado da entrada:

```json
{
  "biblio": {
    "title": "..."
  },
  "body_text": [
    {
      "head_section": "...",
      "text": "..."
    }
  ]
}
```

Observação:

Essa etapa foi criada primeiro pensando no JSON gerado pelo GROBID, mas posteriormente foi mantida porque também pode funcionar com JSONs gerados por outras ferramentas, desde que elas preservem os campos `biblio.title`, `body_text`, `head_section` e `text`.

### Versão 3 — Criação de Lacunas Artificiais

Decisão:

Remover propositalmente um parágrafo da metodologia extraída e substituir o trecho por:

```text
[MISSING_TEXT]
```

Script:

```text
src/3_create_gaps.py
```

Motivação:

A remoção artificial permite conhecer o trecho original removido. Isso cria uma referência para comparar posteriormente com a reconstrução gerada pelo modelo de linguagem.

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

Mudança registrada:

A primeira versão dos arquivos de lacuna continha muitos metadados, como contagem de palavras, posição do trecho, contexto anterior e posterior separados e proporção do texto removido. Esses campos foram removidos porque a prioridade passou a ser testar a forma básica de reconstrução antes de sofisticar a avaliação.

### Versão 4 — Reconstrução com Groq

Decisão:

Usar a API da Groq para testar a reconstrução do trecho ausente com um modelo de linguagem.

Script:

```text
src/4_reconstruct_with_groq.py
```

Motivação:

A Groq foi escolhida por permitir testar modelos de linguagem de forma simples e acessível. Nesta fase, o objetivo não é comparar modelos, mas validar se o fluxo `lacuna -> prompt -> reconstrução` funciona.

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

Mudança registrada:

A primeira versão da reconstrução incluía campos como `confidence`, `notes` e `valid_json_response`. Esses campos foram removidos porque, no momento, o objetivo é apenas testar a reconstrução e comparar o trecho original com o trecho gerado.

### Versão 5 — 2026-06-15 — Mudança de GROBID para PyPDF

Decisão:

Substituir a etapa inicial baseada em GROBID por uma extração baseada em PyPDF.

Novo script:

```text
src/1_extract_text_with_pypdf.py
```

Nova saída:

```text
data/pypdf_output/
```

Motivação:

Durante os testes, o uso do GROBID foi considerado pouco intuitivo e nem sempre assertivo para os PDFs disponíveis. Foi sugerido testar PyPDF como alternativa mais simples, direta e fácil de inspecionar.

O PyPDF não fornece a mesma estrutura semântica do GROBID. Por isso, o novo script cria uma estrutura JSON compatível com a etapa 2, incluindo:

```json
{
  "biblio": {
    "title": "..."
  },
  "body_text": [
    {
      "head_section": "...",
      "text": "...",
      "page": 1
    }
  ]
}
```

Resultado observado:

- o pipeline continuou funcionando até a criação de lacunas;
- a etapa deixou de depender de Docker e serviço local do GROBID;
- o texto extraído ficou mais simples de inspecionar;
- o PyPDF introduziu artefatos de acentuação e quebras de texto em alguns PDFs;
- a identificação de seções passou a depender mais de heurísticas locais;
- em um dos PDFs, a metodologia foi extraída; em outro, a extração ficou vazia por não haver seção metodológica reconhecida.

Consequência técnica:

A etapa `2_extract_method_sections.py` foi ajustada para ler de:

```text
data/pypdf_output/
```

em vez de:

```text
data/grobid_output/
```

Limitação conhecida:

Como o PyPDF extrai texto bruto, a detecção de títulos de seção pode falhar ou gerar artefatos. Uma melhoria futura provável é reforçar o `text_cleaning.py` e melhorar as heurísticas de identificação de seções.

### Versão 6 — 2026-06-15 — Mudança da Fonte dos Artigos para ScienceDirect

Decisão:

Substituir o conjunto anterior de artigos por PDFs obtidos na ScienceDirect:

```text
https://www.sciencedirect.com/
```

Motivação:

A fonte anterior considerada para o corpus era o Semantic Scholar Open Research Corpus. A mudança para ScienceDirect foi motivada pela expectativa de trabalhar com artigos de um mesmo ambiente editorial, com maior padronização visual e estrutural nos PDFs publicados.

Arquivos adicionados para teste:

```text
data/raw_pdfs/1-s2.0-S0167923620301184-main.pdf
data/raw_pdfs/1-s2.0-S0167923621000506-main.pdf
data/raw_pdfs/1-s2.0-S016792362200001X-main.pdf
data/raw_pdfs/1-s2.0-S0167923622001701-main.pdf
data/raw_pdfs/1-s2.0-S0167923623000349-main.pdf
data/raw_pdfs/1-s2.0-S016792362300060X-main.pdf
data/raw_pdfs/1-s2.0-S0167923623002014-main.pdf
data/raw_pdfs/1-s2.0-S0167923624001246-main.pdf
```

Resultado observado no teste inicial:

- os 8 PDFs foram processados com PyPDF;
- 5 dos 8 artigos tiveram seções metodológicas extraídas;
- 3 dos 8 artigos não tiveram metodologia reconhecida pelos padrões atuais;
- a etapa de criação de lacunas funcionou para os 5 artigos com metodologia extraída.

Artigos com metodologia extraída:

```text
1-s2.0-S0167923620301184-main.pdf
1-s2.0-S0167923621000506-main.pdf
1-s2.0-S0167923622001701-main.pdf
1-s2.0-S0167923623000349-main.pdf
1-s2.0-S016792362300060X-main.pdf
```

Artigos sem metodologia reconhecida nesta rodada:

```text
1-s2.0-S016792362200001X-main.pdf
1-s2.0-S0167923623002014-main.pdf
1-s2.0-S0167923624001246-main.pdf
```

Interpretação:

A mudança para ScienceDirect parece positiva para padronizar o corpus, mas não elimina a necessidade de melhorar a identificação das seções metodológicas. Alguns artigos usam títulos como `Data`, `Case study`, `Framework`, `Model`, `Data preparation` ou outros nomes que podem representar partes metodológicas, mas que ainda não são capturados de forma consistente pelos padrões atuais.

Mudança técnica associada:

As etapas 1, 2 e 3 passaram a limpar arquivos `.json` antigos nas pastas de saída antes de gerar novos resultados. Isso evita que saídas de rodadas anteriores contaminem a análise do corpus atual.

### Versão 7 — 2026-06-15 — Extração de Metodologias Assistida por Groq

Decisão:

Alterar a etapa de extração de metodologias para usar o modelo da Groq como classificador dos blocos extraídos pelo PyPDF.

Motivação:

Após a mudança para artigos da ScienceDirect, observou-se que os documentos possuem estrutura editorial semelhante, mas nem sempre apresentam uma seção explicitamente chamada `Methodology`, `Methods` ou equivalente.

Em vários artigos, o conteúdo metodológico pode estar distribuído em seções como:

```text
Data
Dataset
Case study
Data preparation
Feature selection
Predictive modeling
Model development
Framework
Evaluation metrics
```

A abordagem anterior, baseada apenas em padrões e heurísticas, não capturava todos esses casos de forma consistente. Por isso, foi adotada uma camada assistida por LLM para decidir quais blocos de texto pertencem à metodologia.

Estratégia adotada:

O PyPDF continua responsável pela extração inicial do texto. Em seguida, o script `2_extract_method_sections.py` envia ao modelo uma lista numerada de blocos extraídos, contendo:

```text
índice do bloco
título de seção identificado
página
prévia do texto
```

O modelo não deve reescrever nem resumir a metodologia. Ele deve apenas retornar os índices dos blocos que pertencem à metodologia.

Formato esperado da resposta do modelo:

```json
{
  "method_block_indexes": [0, 1, 2]
}
```

Justificativa metodológica:

Essa abordagem mantém o processo mais controlado do que pedir ao modelo para "extrair a metodologia" livremente. O modelo atua como classificador/selecionador de blocos já existentes, reduzindo o risco de geração de texto novo, omissão arbitrária ou reescrita indevida.

Consequência técnica:

A etapa `2_extract_method_sections.py` passou a depender da variável:

```text
GROQ_API_KEY
```

e usa o mesmo modelo definido em:

```text
GROQ_MODEL
```

Limitação conhecida:

Mesmo com LLM, a qualidade da extração depende da qualidade dos blocos produzidos pelo PyPDF. Se a extração inicial quebrar mal o texto ou misturar seções diferentes em um mesmo bloco, o modelo pode selecionar blocos parcialmente corretos.

Resultado observado:

A abordagem assistida por Groq funcionou em teste limitado, mas encontrou restrições práticas de uso por causa do limite curto da conta gratuita. Em uma tentativa com mais artigos, houve problema de limite de tokens/requisições, tornando essa estratégia menos adequada para a etapa de extração em lote.

### Versão 8 — 2026-06-16 — Retorno para Extração por Padrões Ampliados

Decisão:

Remover o uso de LLM da etapa de extração de metodologias e voltar para uma abordagem determinística baseada em padrões de títulos de seção.

Motivação:

Após a tentativa com Groq, concluiu-se que usar LLM para extração de seções poderia ser desnecessário nesta fase. O novo conjunto de artigos, agora do periódico Knowledge-Based Systems, apresentou títulos de seção mais padronizados e recorrentes. Isso tornou viável ampliar a lista de variações metodológicas em vez de depender de chamadas ao modelo.

Nova estratégia:

O arquivo `config/section_patterns.json` passou a conter uma lista mais abrangente de seções que podem representar metodologia em artigos de machine learning, incluindo termos como:

```text
Methodology
Material and method
Experimental procedure
Proposed method
Proposed approach
Data pre-processing
Dataset
Feature extraction
Feature engineering
Feature selection
Machine learning algorithms
Model validation strategy
Evaluation metrics
Case study
Training instances
Settings and metrics
```

Também foram adicionados padrões de parada para evitar a captura de seções de resultado, discussão, conclusão e referências.

Consequência técnica:

A etapa `2_extract_method_sections.py` deixou de depender de:

```text
GROQ_API_KEY
GROQ_MODEL
```

e voltou a funcionar localmente, sem chamadas externas.

Resultado observado:

Nos 10 PDFs do periódico Knowledge-Based Systems testados nesta rodada:

- os 10 PDFs foram processados pelo PyPDF;
- os 10 artigos tiveram blocos metodológicos extraídos;
- a etapa de criação de lacunas funcionou para os 10 artigos;
- alguns falsos positivos ainda apareceram por causa de ruídos do PyPDF, ligaturas, tabelas e títulos quebrados, mas a cobertura geral foi melhor que nas rodadas anteriores.

Interpretação:

A abordagem por padrões ampliados é mais simples, barata e reprodutível para a fase atual. O Groq permanece reservado para a etapa de reconstrução textual, onde o uso de modelo de linguagem é mais necessário.

### Versão 9 — 2026-06-16 — GROBID como Extrator Principal sem Fallback

Decisão:

Retornar ao GROBID como ferramenta principal da etapa 1 e remover o PyPDF do fluxo ativo do projeto.

Script atual da etapa 1:

```text
src/1_parse_with_grobid.py
```

Saída atual da etapa 1:

```text
data/grobid_output/
```

Motivação:

Após comparar as extrações do PyPDF e do GROBID no conjunto atual de artigos do periódico Knowledge-Based Systems, o GROBID apresentou melhor resultado para o objetivo do projeto. Embora exija Docker e um serviço local em execução, ele produz uma representação mais adequada para artigos científicos, com campos estruturados como `biblio`, `body_text`, `head_section` e `text`.

Resultado observado na comparação:

- o GROBID processou os 10 PDFs testados sem erro;
- foram gerados 10 arquivos JSON e 10 arquivos TEI XML;
- a extração por GROBID preservou melhor a separação de blocos textuais;
- a etapa de extração de metodologias encontrou blocos metodológicos nos 10 artigos;
- o PyPDF foi mais simples de executar, mas produziu mais ruídos de texto, quebras, ligaturas e dependência de heurísticas para reconstruir a estrutura do artigo.

Limitação conhecida:

Em alguns arquivos, o título identificado pelo GROBID pode aparecer de forma genérica ou incorreta, como `Knowledge-Based Systems`. Essa limitação não impede a extração das metodologias nesta fase, pois o objetivo principal da etapa 2 depende dos blocos do corpo do texto e dos títulos de seção. A correção de metadados pode ser tratada depois, por exemplo usando nome do arquivo, DOI ou metadados bibliográficos.

Decisão sobre fallback:

Não será implementado fallback automático para PyPDF neste momento. A decisão foi reduzir a complexidade do pipeline e manter uma única fonte de extração textual. O PyPDF permanece registrado neste documento como experimento anterior, mas não faz parte do fluxo principal atual.

Fluxo consolidado:

```text
data/raw_pdfs/
  -> data/grobid_output/
  -> data/methods_extracted/
  -> data/gaps/
  -> results/reconstructions/
```

### Versão 10 — 2026-06-16 — Troca da Reconstrução de Groq para Gemini

Decisão:

Substituir a etapa de reconstrução com Groq por uma implementação usando Gemini via Google AI Studio.

Novo script da etapa 4:

```text
src/4_reconstruct_with_gemini.py
```

Motivação:

A mudança foi motivada principalmente pelo limite curto da conta gratuita da Groq durante os testes. Como o Google AI Studio aparenta oferecer uma margem maior de tokens gratuitos, o Gemini passa a ser uma opção melhor para testar a reconstrução dos trechos ausentes sem alterar as etapas anteriores do pipeline.

Escopo da mudança:

A alteração afeta apenas a etapa de reconstrução textual. O restante do fluxo permanece igual:

```text
GROBID
  -> extração de metodologias por padrões
  -> criação de lacunas artificiais
  -> reconstrução com Gemini
```

Configuração:

O script lê a chave no arquivo `.env` usando o nome:

```text
gemini-api-key
```

Também é possível definir o modelo com:

```text
gemini-model
```

Modelo padrão:

```text
gemini-flash-latest
```

Justificativa técnica:

A chamada foi implementada diretamente com HTTP, seguindo o exemplo de `curl` do Google AI Studio. Isso evita adicionar um SDK novo nesta fase e mantém a etapa simples para teste.

### Registro — 2026-06-23 — Teste de Alternativas ao GROBID

Foi realizado um teste experimental de extração textual usando `pypdf.PdfReader`, `PyPDF2.PdfReader` e `PyMuPDF`, apenas para comparar com as extrações já feitas com GROBID. As alternativas conseguiram extrair texto dos PDFs, mas dependeram de heurísticas mais frágeis para reconstruir blocos e títulos de seção. Na comparação inicial, o GROBID continuou se mostrando a melhor opção para o projeto por entregar uma estrutura mais adequada para artigos científicos e para a extração posterior das metodologias.

### Registro — 2026-06-23 — Refinamento dos Padrões de Metodologia

Após auditar os arquivos em `data/methods_extracted/`, foram removidos padrões muito amplos que capturavam ruído, como `data`, `experiment`, `machine learning algorithms` e `correlation heatmap`. Também foram adicionadas seções administrativas aos padrões de parada, como `Data availability`, `Data and code availability`, `Availability of data and material`, `Ethical approval` e `Declaration of competing interest`. Em seguida, foram incluídas variações metodológicas mais específicas, como `data segmentation`, `data splitting`, `input the dataset`, `feature normalization` e subtítulos do procedimento FCM/RF/SHAP. A extração ficou mais limpa e os 10 artigos continuaram aproveitáveis para o protótipo, sem necessidade imediata de excluir algum PDF.

### Registro — 2026-06-23 — Teste Experimental com OpenRouter

Foi criado um passo separado para testar modelos gratuitos via OpenRouter usando os mesmos arquivos de lacuna gerados em `data/gaps/`. O objetivo é comparar a reconstrução produzida por diferentes LLMs sem substituir a etapa principal com Gemini. O script `src/5_test_openrouter_models.py` usa a variável `OPENROUTER_API_KEY`, permite testar `openrouter/free`, uma lista de modelos gratuitos específicos ou um modelo informado manualmente, e salva os resultados em `results/openrouter_tests/`.

Após os primeiros testes com Gemini e OpenRouter, os prompts de reconstrução foram traduzidos para inglês, pois o corpus atual contém artigos em inglês. Também foi realizado um teste comparativo no artigo em que o Gemini apresentou a reconstrução mais estável (`A-fuzzy-logic-driven...`). Parte dos modelos gratuitos do OpenRouter retornou reconstruções válidas, enquanto outros falharam por limite temporário, timeout ou por não serem modelos de chat adequados ao endpoint usado.

### Registro — 2026-09-11 — Validação Estruturada com Pydantic

Foi adicionada uma validação com Pydantic para as respostas dos modelos de linguagem. O objetivo é impedir que respostas vazias, JSONs aninhados, textos contendo o marcador `[MISSING_TEXT]` ou saídas fora do schema sejam salvas como reconstruções válidas. A validação foi centralizada em `src/llm_response_schema.py` e passou a ser usada tanto no script do Gemini quanto no script de testes com OpenRouter.

## Decisões de Organização do Código

Os scripts executáveis do pipeline foram numerados para facilitar a ordem de uso:

```text
1_parse_with_grobid.py
2_extract_method_sections.py
3_create_gaps.py
4_reconstruct_with_gemini.py
5_test_openrouter_models.py
```

Os arquivos auxiliares permaneceram sem numeração:

```text
llm_response_schema.py
text_cleaning.py
utils.py
```

Justificativa:

A numeração ajuda a entender a sequência experimental. Os arquivos auxiliares não representam etapas executáveis do pipeline e, por isso, foram mantidos sem prefixo numérico.

## Próximos Pontos a Registrar

Este documento deve ser atualizado sempre que houver mudança relevante no rumo do projeto, por exemplo:

- alteração na estratégia de extração das metodologias;
- comparação entre GROBID e PyPDF;
- troca ou comparação de modelos de linguagem;
- inclusão de etapa de avaliação automática;
- inclusão de avaliação qualitativa;
- mudança no formato dos arquivos intermediários;
- problemas encontrados durante testes com PDFs reais;
- decisões tomadas para simplificar ou expandir o escopo.
