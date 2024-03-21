#%% Importando bibliotecas
import sidrapy as sidra
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

#%% Configurando graficos

 # Configuração das cores
plt.rcParams['axes.titlesize'] = 16
plt.rcParams['axes.titlecolor'] = 'w'
plt.rcParams['axes.labelsize'] = 14 
plt.rcParams['axes.labelcolor'] = 'w'
plt.rcParams['figure.facecolor'] = 'black'
plt.rcParams['axes.facecolor'] = 'black'
plt.rcParams['xtick.color'] = 'w'
plt.rcParams['ytick.color'] = 'w'
plt.rcParams['grid.color'] = 'gray'
plt.rcParams['grid.linestyle'] = ':'
plt.rcParams['grid.linewidth'] = 0.5 
plt.rcParams['axes.autolimit_mode'] = 'data'
plt.rcParams['axes.axisbelow'] = True
plt.rcParams['legend.labelcolor'] = 'white'


#%% criando as bases
dados_brutos = list(
    map(
        # função com argumentos que será repetida
        lambda tabela, variavel:(
            sidra.get_table(
                table_code=tabela,
                territorial_level=1,
                ibge_territorial_code= 'all',
                variable=variavel,
                classifications={ # PIB preços consultar no site da sidra
                    "11255": "90687,90691,90696,90707,93404,93405,93406,93407,93408"
                    },
                period='all'
            )
        ),
        # códigos das tabelas (pro argumento tabela)
        ["1620", "1621", "1846", "6612", "6613"],

        # códigos da variável dentro da tabela (pro argumento variavel)
        ["583", "584", "585", "9318", "9319"]
    )
)


#%%Tratamento de dados

dados = (
    pd.concat(
        objs=dados_brutos,
        keys=["num_indice", "num_indice_sa", "precos_correntes",
                "precos_constantes", "precos_constantes_sa"],
        names = ["tabela", "linha"]
    )
    .reset_index()
    .rename(columns=dados_brutos[0].iloc[0])
    .query('Variável not in "Variável"')
    .rename(
        columns = {
            "Trimestre (Código)": "data",
            "Setores e subsetores": "rubrica",
            "Valor": "valor"
            }
    )    
    .filter(items = ['tabela', 'data', 'rubrica', 'valor'], axis = 'columns')
    .replace(
        to_replace ={
                "rubrica": {
                "Agropecuária - total": "Agropecuária",
                "Indústria - total": "Indústria",
                "Serviços - total": "Serviços",
                "PIB a preços de mercado": "PIB",
                "Despesa de consumo das famílias": "Consumo das Famílias",
                "Despesa de consumo da administração pública": "Despesa do Governo",
                "Formação bruta de capital fixo": "FBFC",
                "Exportação de bens e serviços": "Exportação",
                "Importação de bens e serviços (-)": "Importação"
                }
                }
             )
    .assign(  # substitui o 5º caracter da coluna data por "-Q" e converte em YYYY-MM-DD
        data = lambda x: pd.to_datetime(
            x.data.str.slice_replace(start = 4, stop = 5, repl = "-Q")
            ),
        valor = lambda x: x.valor.astype(float)
    )
)

#%% Variação das taxas
taxas = (
    dados.query("tabela in ['num_indice', 'num_indice_sa']")
    .pivot(index = ["data", "rubrica"], columns = "tabela", values = "valor")
    .reset_index()
    .sort_values("data") # ordena ascedentemente pela coluna data
    )
# cria novas colunas/cálculo por grupo (rubrica) feito dentro do apply()

taxas["var_margem"] = (
    taxas.groupby("rubrica", group_keys=False)["num_indice_sa"] # agrupa os dados e aponta a coluna
    .apply(lambda x: x.pct_change(1) * 100)   # calcula a variação na coluna
)
taxas["var_interanual"] = (
    taxas.groupby("rubrica", group_keys=False)["num_indice"]
    .apply(lambda x: x.pct_change(4) * 100)
)
taxas["var_anual"] = (
    taxas.groupby("rubrica", group_keys=False)["num_indice"] # soma móvel de 4 períodos
    .apply(lambda x: (x.rolling(4).sum() / x.rolling(4).sum().shift(4) - 1) * 100)
)
taxas["ano"] = taxas["data"].dt.year
taxas["num_indice_acum"] = (
    taxas.groupby(["rubrica", "ano"], group_keys=False)["num_indice"]
    .apply(lambda x: x.cumsum()) # acumula o número índice por ano/rubrica
    )
taxas["var_acum_ano"] = (
    taxas.groupby("rubrica", group_keys=False)["num_indice_acum"]
    .apply(lambda x: x.pct_change(4) * 100)
)
#%% plots variações
PIB_var = taxas.query("rubrica == 'PIB'"
                  ).filter(
        items = ["data", "var_margem", "var_interanual", "var_anual", "var_acum_ano"],
        axis = "columns"
        ).set_index('data')

plt.subplots(figsize=(12,6),sharex=True)
plt.suptitle('PIB: Taxas de variação\nDados: IBGE | Elaboração: Caio Ferreira', 
             fontsize=14, color='w')
plt.subplots_adjust(hspace=0.45)  # Ajusta o espaço vertical entre os subplots
plt.tight_layout()  # Ajusta automaticamente os subplots para evitar sobreposições

for i in range(221,225):
    coluna =["var_margem", "var_interanual", "var_anual", "var_acum_ano"]
    cor = ['b']
    plt.subplot(i)
    plt.plot(PIB_var.index,PIB_var[f'{coluna[i-221]}'],color= '#282f6b')
    plt.ylabel(coluna[i-221	],color='w')
    plt.xticks(rotation=45)
    plt.locator_params(axis='y', nbins=10)
    plt.grid(True)
plt.savefig(r'C:\Users\caiof\OneDrive\Repositório\PIB_Crescimento\Graficos PIB\Taxa_variacao_PIB')
plt.show()


#%%
taxas_final = (
    taxas.query("data == data.max()")
    .filter(
        items = ["rubrica", "var_margem", "var_interanual", "var_anual", "var_acum_ano"],
        axis = "columns"
        )
    .set_index("rubrica")
    )



# %% deflator do PIB
deflator = (
    dados.query(
        "tabela in ['precos_correntes', 'precos_constantes'] and rubrica == 'PIB'"
        )
    .pivot(
        index = "data",
        columns = "tabela",
        values = "valor"
        )
    .assign(
        deflator = lambda x: x.precos_correntes / x.precos_constantes * 100,
        var_anual = lambda x: (
            x.deflator.rolling(4).sum() / x.deflator.shift(4).rolling(4).sum() - 1
            ) * 100
        )
    )

#%% decomposicao
decomposicao = (
    dados.query("rubrica == 'PIB' and tabela == 'precos_constantes_sa'")
    .assign(
        A = lambda x: x.valor.rolling(4).mean().shift(4),
        B = lambda x: x.valor.shift(4),
        C = lambda x: x.valor.rolling(4).mean(),
        carrego = lambda x: (x.B - x.A) / x.A * 100,
        cres_ano = lambda x: (x.C - x.B) / x.A * 100,
        total = lambda x: x.carrego + x.cres_ano
        )
    .query("data.dt.quarter == 4")
    .assign(ano = lambda x: x.data.dt.year)
    .filter(items = ["ano", "carrego", "cres_ano", "total"])
    .rename(columns = {
        "carrego": "Carrego Estatístico",
        "cres_ano": "Crescimento no Ano",
        "total": "Crescimento Anual"
        }
        )
    )

#%%plot da decompizição
fig_decomposicao = decomposicao[['ano', 'Crescimento Anual']].plot(
    x='ano',
    linestyle = "dashed",
    color = 'gray',
    marker = "o",
    use_index = False,

)
fig_decomposicao = decomposicao[["ano", "Carrego Estatístico", "Crescimento no Ano"]].plot( # coluna
    x = "ano",
    kind = "bar",
    stacked = True,
    ax = fig_decomposicao, # "adiciona" os dois em um mesmo gráfico
    width = 0.9,
    figsize = (12,6),
    color = {"Carrego Estatístico": "#b22200", "Crescimento no Ano": "#282f6b"},
    ylabel = "%",
    grid = True,
    title = "Decomposição do PIB\nContribuição ao crescimento anual\nDados:" +
    " IBGE | Elaboração: Caio Ferreira"
)

fig_decomposicao.set_xticklabels(fig_decomposicao.get_xticklabels(), rotation=45)
plt.locator_params(axis='y', nbins=10)
plt.savefig(r'C:\Users\caiof\OneDrive\Repositório\PIB_Crescimento' \
            r'\Graficos PIB\PIB - Carrego e Crescimento.png')

plt.show()