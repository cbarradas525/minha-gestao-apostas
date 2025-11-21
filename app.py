import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Pro Cloud", layout="wide")
st.title("⚽ Gestão de Banca (Google Sheets)")

# --- CONEXÃO COM GOOGLE SHEETS ---
# Conecta à planilha
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados():
    try:
        # Lê os dados da aba 'Página1' (ou Sheet1)
        df = conn.read(worksheet="Página1", ttl="0") # ttl=0 para não usar cache antigo
        # Garante que a data seja interpretada corretamente
        if not df.empty and 'data_jogo' in df.columns:
            df['data_jogo'] = pd.to_datetime(df['data_jogo'])
        return df
    except Exception as e:
        st.error("Erro ao conectar na Planilha. Verifique se configurou os Segredos (Secrets) no Streamlit Cloud.")
        st.stop()

def salvar_no_google(df_novo):
    try:
        # Atualiza a planilha com o novo DataFrame
        conn.update(worksheet="Página1", data=df_novo)
        st.cache_data.clear() # Limpa cache para forçar atualização
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- FUNÇÕES DE LÓGICA ---
def adicionar_aposta(nova_linha):
    df = carregar_dados()
    # Se a planilha estiver vazia ou nova, cria o DataFrame
    if df.empty:
        df = pd.DataFrame(columns=['data_jogo', 'liga', 'time_casa', 'time_fora', 'mercado', 
                                   'probabilidade_site', 'odd_referencia', 'casa_aposta', 
                                   'odd_apostada', 'valor_aposta', 'resultado', 'lucro_prejuizo'])
    
    # Adiciona a nova linha
    df = pd.concat([df, pd.DataFrame([nova_linha])], ignore_index=True)
    salvar_no_google(df)

def atualizar_status(index_real, novo_resultado, novo_lucro):
    df = carregar_dados()
    # Atualiza as colunas específicas
    df.at[index_real, 'resultado'] = novo_resultado
    df.at[index_real, 'lucro_prejuizo'] = novo_lucro
    salvar_no_google(df)

# --- INTERFACE ---
menu = st.sidebar.selectbox("Menu", ["Dashboard", "Registrar Aposta", "Gerenciar Resultados"])

if menu == "Dashboard":
    st.header("📊 Performance Global")
    df = carregar_dados()
    
    if not df.empty:
        # Converter colunas numéricas caso venham como texto da planilha
        df['lucro_prejuizo'] = pd.to_numeric(df['lucro_prejuizo'], errors='coerce').fillna(0)
        df['valor_aposta'] = pd.to_numeric(df['valor_aposta'], errors='coerce').fillna(0)
        
        # Filtros e Métricas
        df_final = df[df['resultado'] != 'Pendente']
        
        lucro = df_final['lucro_prejuizo'].sum()
        total_investido = df_final['valor_aposta'].sum()
        roi = (lucro / total_investido * 100) if total_investido > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Lucro", f"R$ {lucro:.2f}")
        col2.metric("ROI", f"{roi:.2f}%")
        col3.metric("Total Apostas", len(df_final))
        
        st.divider()
        
        # Gráfico de Evolução
        if not df_final.empty:
            st.subheader("Evolução da Banca")
            df_grafico = df_final.sort_values(by='data_jogo').reset_index()
            df_grafico['Acumulado'] = df_grafico['lucro_prejuizo'].cumsum()
            st.line_chart(df_grafico['Acumulado'])
    else:
        st.info("A planilha está vazia. Registre uma aposta!")

elif menu == "Registrar Aposta":
    st.header("📝 Registrar")
    with st.form("nova_aposta", clear_on_submit=True):
        c1, c2 = st.columns(2)
        data = c1.date_input("Data", datetime.now())
        liga = c1.text_input("Liga")
        casa = c1.text_input("Casa")
        fora = c1.text_input("Fora")
        mercado = c1.selectbox("Mercado", ["Over 1.5", "Under 3.5", "Match Odds"])
        
        bookie = c2.selectbox("Casa", ["Bet365", "Betfair", "Pinnacle"])
        odd = c2.number_input("Odd", value=1.50)
        valor = c2.number_input("Valor", value=50.0)
        
        if st.form_submit_button("Salvar na Nuvem"):
            nova_aposta = {
                'data_jogo': data, 'liga': liga, 'time_casa': casa, 'time_fora': fora,
                'mercado': mercado, 'probabilidade_site': 0, 'odd_referencia': 0,
                'casa_aposta': bookie, 'odd_apostada': odd, 'valor_aposta': valor,
                'resultado': 'Pendente', 'lucro_prejuizo': 0
            }
            adicionar_aposta(nova_aposta)
            st.success("Salvo na planilha do Google!")

elif menu == "Gerenciar Resultados":
    st.header("📋 Pendentes")
    df = carregar_dados()
    if not df.empty:
        # Filtra pendentes mantendo o índice original para poder editar
        pendentes = df[df['resultado'] == 'Pendente']
        
        if not pendentes.empty:
            for i, row in pendentes.iterrows():
                cols = st.columns([3, 1, 1, 1])
                cols[0].write(f"{row['time_casa']} x {row['time_fora']} ({row['mercado']})")
                cols[1].write(f"Odd: {row['odd_apostada']}")
                
                res = cols[2].selectbox("Status", ["Pendente", "Green", "Red"], key=f"s_{i}", label_visibility="collapsed")
                
                if cols[3].button("Salvar", key=f"b_{i}"):
                    lucro = 0
                    if res == "Green": lucro = (float(row['valor_aposta']) * float(row['odd_apostada'])) - float(row['valor_aposta'])
                    elif res == "Red": lucro = -float(row['valor_aposta'])
                    
                    atualizar_status(i, res, lucro)
                    st.rerun()
        else:
            st.success("Nenhuma aposta pendente.")
