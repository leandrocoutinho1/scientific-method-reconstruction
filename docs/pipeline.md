# Visão geral do pipeline

Este documento descreve o fluxo inicial do protótipo para reconstrução automática de partes faltantes em seções metodológicas de artigos científicos.

## Etapa 1 — Coleta dos artigos científicos

Selecionar um conjunto pequeno de artigos científicos relacionados a aplicações de aprendizado de máquina. Nesta etapa inicial, a recomendação é começar com poucos documentos, por exemplo 10 artigos, para validar o funcionamento do processo antes de expandir o corpus.

Os arquivos PDF devem ser armazenados em:

```text
data/raw_pdfs/
```

## Etapa 2 — Processamento dos PDFs com GROBID

Utilizar o GROBID para converter os PDFs em representações estruturadas, como TEI/XML e JSON. Essa etapa permite obter informações sobre título, autores, resumo, corpo do texto, seções e referências.

Script utilizado:

```bash
python src/parse_with_grobid.py
```

Entrada:

```text
data/raw_pdfs/
```

Saída:

```text
data/grobid_output/
```

## Etapa 3 — Extração das seções metodológicas

Após o processamento com GROBID, o sistema analisa os arquivos JSON gerados e tenta identificar automaticamente seções relacionadas à metodologia.

Exemplos de títulos de seção considerados:

- Métodos
- Metodologia
- Materiais e Métodos
- Procedimentos Metodológicos
- Método Proposto
- Experimentos
- Configuração Experimental
- Methods
- Methodology
- Materials and Methods
- Experimental Setup

Script utilizado:

```bash
python src/extract_method_sections.py
```

Entrada:

```text
data/grobid_output/
```

Saída:

```text
data/methods_extracted/
```

## Etapa 4 — Criação de lacunas artificiais

Depois de extrair as metodologias, o sistema remove artificialmente uma parte do texto para simular um documento incompleto. O trecho removido é armazenado separadamente para permitir comparação posterior com a reconstrução gerada pelo modelo de linguagem.

Script utilizado:

```bash
python src/create_gaps.py
```

Entrada:

```text
data/methods_extracted/
```

Saída:

```text
data/gaps/
```

Cada arquivo gerado contém:

- texto original da metodologia;
- texto com a lacuna marcada por `[MISSING_TEXT]`;
- trecho original removido;
- posição inicial e final da lacuna.

## Etapa 5 — Reconstrução dos trechos ausentes

Nesta etapa, o texto com a lacuna será enviado a um modelo de linguagem. O modelo deverá gerar uma reconstrução plausível para o trecho marcado como `[MISSING_TEXT]`, considerando o contexto anterior e posterior da metodologia.

Esta etapa ainda será implementada em uma fase posterior do projeto.

## Etapa 6 — Avaliação dos resultados

A avaliação será feita comparando o trecho reconstruído com o trecho original removido artificialmente. A análise poderá considerar métricas automáticas e também uma avaliação qualitativa.

Possíveis critérios de avaliação:

- coerência textual;
- plausibilidade metodológica;
- aderência ao estilo científico;
- similaridade com o trecho original;
- limitações observadas nas reconstruções.

## Observações iniciais

Durante os testes, é importante registrar:

- quais PDFs foram processados corretamente;
- quais artigos tiveram metodologia extraída com sucesso;
- quais documentos falharam;
- quais nomes de seção não foram reconhecidos;
- quais problemas ocorreram na extração do texto;
- quais ajustes foram necessários nos padrões de busca.

Essas informações poderão ser utilizadas posteriormente na escrita do capítulo de desenvolvimento e na discussão das limitações do trabalho.
