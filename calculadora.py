import streamlit as st
import plotly.graph_objects as go
import math

# --- LÓGICA MATEMÁTICA E REGRAS DE NEGÓCIO ---

def calcular_dimensoes_e_peso(itens):
    if not itens:
        return 0, 0, 0, 0
    x_total = sum(item['x'] for item in itens)
    y_max = max(item['y'] for item in itens)
    z_max = max(item['z'] for item in itens)
    peso_total = sum(item['peso'] for item in itens)
    return x_total, y_max, z_max, peso_total

def atende_limite(x, y, z, peso, modalidade):
    # AGORA COM LIMITES ABSOLUTOS DE COMPRIMENTO (EIXO X)
    if modalidade == 'ePacket': 
        return x <= 600 and (x + y + z) <= 900 and peso <= 2000
    elif modalidade == 'Air Parcel': 
        return x <= 1050 and (x + 2 * (y + z)) <= 2000 and peso <= 30000
    elif modalidade == 'EMS': 
        return x <= 1500 and (x + 2 * (y + z)) <= 3000 and peso <= 30000
    return False

def estimar_frete_jpy(modalidade, peso_g):
    if peso_g == 0: return 0
        
    if modalidade == 'ePacket':
        if peso_g > 2000: return None
        if peso_g <= 100: return 920
        degraus = math.ceil((peso_g - 100) / 100)
        return 920 + (degraus * 260)
            
    elif modalidade == 'Air Parcel':
        if peso_g > 30000: return None
        if peso_g <= 1000:
            return 4550
        elif peso_g <= 10000:
            kg_extra = math.ceil((peso_g - 1000) / 1000)
            return 4550 + (kg_extra * 2700)
        else:
            kg_extra = math.ceil((peso_g - 10000) / 1000)
            return 28850 + (kg_extra * 1800)
        
    elif modalidade == 'EMS':
        if peso_g > 30000: return None
        if peso_g <= 500:
            return 3600
        elif peso_g <= 2000:
            degraus = math.ceil((peso_g - 500) / 100)
            return 3600 + (degraus * 300)
        elif peso_g <= 6000:
            degraus = math.ceil((peso_g - 2000) / 500)
            return 8100 + (degraus * 1500)
        else:
            degraus = math.ceil((peso_g - 6000) / 1000)
            return 20100 + (degraus * 2400)
        
    return None

def empacotar_itens(itens, modalidade):
    caixas = []
    for item in itens:
        alocado = False
        for caixa in caixas:
            teste_itens = caixa + [item]
            x_teste, y_teste, z_teste, peso_teste = calcular_dimensoes_e_peso(teste_itens)
            if atende_limite(x_teste, y_teste, z_teste, peso_teste, modalidade):
                caixa.append(item)
                alocado = True
                break
        if not alocado:
            if atende_limite(item['x'], item['y'], item['z'], item['peso'], modalidade):
                caixas.append([item])
            else:
                return f"❌ O item '{item['nome']}' excede os limites de comprimento, volume ou peso do {modalidade} mesmo sozinho!"
    return caixas

# --- LÓGICA VISUAL (GRÁFICOS 3D) ---
def gerar_grafico_3d(caixa_itens, x_caixa, y_caixa, z_caixa):
    fig = go.Figure()
    pos_x_atual = 0
    cores = ['#FF9999', '#66B2FF', '#99FF99', '#FFCC99', '#FF99CC', '#E0E0E0', '#B266FF']
    
    for i, item in enumerate(caixa_itens):
        cor = cores[i % len(cores)]
        nome = item['nome']
        dx, dy, dz = item['x'], item['y'], item['z']
        
        x = [pos_x_atual, pos_x_atual, pos_x_atual+dx, pos_x_atual+dx,
             pos_x_atual, pos_x_atual, pos_x_atual+dx, pos_x_atual+dx]
        y = [0, dy, dy, 0, 0, dy, dy, 0]
        z = [0, 0, 0, 0, dz, dz, dz, dz]
        
        i_faces = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j_faces = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k_faces = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
        
        fig.add_trace(go.Mesh3d(
            x=x, y=y, z=z,
            i=i_faces, j=j_faces, k=k_faces,
            color=cor,
            opacity=0.9,
            name=nome,
            hoverinfo='name',
            flatshading=True
        ))
        pos_x_atual += dx

    x_ext = [0, x_caixa, x_caixa, 0, 0, 0, x_caixa, x_caixa, 0, 0, x_caixa, x_caixa, x_caixa, x_caixa, 0, 0]
    y_ext = [0, 0, y_caixa, y_caixa, 0, 0, 0, y_caixa, y_caixa, 0, 0, 0, y_caixa, y_caixa, y_caixa, y_caixa]
    z_ext = [0, 0, 0, 0, 0, z_caixa, z_caixa, z_caixa, z_caixa, z_caixa, z_caixa, 0, 0, z_caixa, z_caixa, 0]
    
    fig.add_trace(go.Scatter3d(
        x=x_ext, y=y_ext, z=z_ext,
        mode='lines',
        line=dict(color='red', width=4, dash='dash'),
        name='Caixa Externa (Limites)',
        hoverinfo='none'
    ))

    # FUNDO BRANCO E ESTILIZAÇÃO DO GRÁFICO
    fig.update_layout(
        paper_bgcolor='white', # Fundo atrás do gráfico
        plot_bgcolor='white',
        font=dict(color='black'), # Letras em preto para contrastar
        scene=dict(
            xaxis=dict(title='X (mm)', backgroundcolor='white', gridcolor='lightgray', showbackground=True, zerolinecolor='lightgray'),
            yaxis=dict(title='Y (mm)', backgroundcolor='white', gridcolor='lightgray', showbackground=True, zerolinecolor='lightgray'),
            zaxis=dict(title='Z (mm)', backgroundcolor='white', gridcolor='lightgray', showbackground=True, zerolinecolor='lightgray'),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- INTERFACE VISUAL DO APLICATIVO ---
st.set_page_config(page_title="Calculadora de Frete", page_icon="📦", layout="wide")
st.title("📦 Calculadora de Envios Internacionais")

st.warning("⚠️ **Aviso:** Se as medidas finais ficarem muito justas ao limite do frete, pode não ser possível o envio. Lembre-se de deixar uma margem de segurança para acomodar a própria espessura da caixa de papelão, plástico bolha e outros materiais de proteção.")

st.write("Digite o nome, as dimensões (em mm) e o peso (em gramas). O algoritmo calculará o valor exato segundo a tabela do Japan Post (América do Sul).")

num_figures = st.number_input("Quantos itens vai enviar?", min_value=1, max_value=15, value=1)

itens_para_envio = []

for i in range(num_figures):
    st.markdown(f"**Item {i+1}**")
    col0, col1, col2, col3, col4 = st.columns([2, 1, 1, 1, 1]) 
    
    with col0:
        nome_item = st.text_input("Nome", value=f"Figure {i+1}", key=f"nome_{i}")
    with col1:
        m1 = st.number_input("Med. 1 (mm)", min_value=1, value=300, key=f"m1_{i}")
    with col2:
        m2 = st.number_input("Med. 2 (mm)", min_value=1, value=200, key=f"m2_{i}")
    with col3:
        m3 = st.number_input("Med. 3 (mm)", min_value=1, value=150, key=f"m3_{i}")
    with col4:
        peso = st.number_input("Peso (g)", min_value=1, value=1500, key=f"peso_{i}")
        
    dimensoes = sorted([m1, m2, m3], reverse=True)
    
    itens_para_envio.append({
        'nome': nome_item,
        'x': dimensoes[0],
        'y': dimensoes[1],
        'z': dimensoes[2],
        'peso': peso
    })

st.divider()

if st.button("Calcular Empacotamento e Custos", type="primary", use_container_width=True):
    modalidades = ['ePacket', 'Air Parcel', 'EMS']
    
    for mod in modalidades:
        st.subheader(f"✈️ Frete: {mod}")
        resultado = empacotar_itens(itens_para_envio, mod)
        
        if isinstance(resultado, str):
            st.error(resultado)
        else:
            custo_total_jpy = 0
            st.success(f"Total de caixas necessárias: {len(resultado)}")
            
            for idx, caixa in enumerate(resultado):
                nomes = [item['nome'] for item in caixa]
                x, y, z, peso_caixa = calcular_dimensoes_e_peso(caixa)
                volumetria = x + 2*(y+z) if mod != 'ePacket' else x+y+z
                
                valor_frete = estimar_frete_jpy(mod, peso_caixa)
                
                if valor_frete:
                    custo_total_jpy += valor_frete
                    texto_frete = f"¥ {valor_frete:,.0f}"
                else:
                    texto_frete = "Erro no cálculo de peso"
                
                with st.expander(f"📦 Caixa {idx+1} ({len(caixa)} itens) | Peso: {peso_caixa}g | Frete Exato: {texto_frete}"):
                    st.write(f"**Conteúdo:** {', '.join(nomes)}")
                    st.write(f"**Dimensões Finais Estimadas:** X={x}mm, Y={y}mm, Z={z}mm | Volumetria: {volumetria}mm")
                    
                    figura_grafico = gerar_grafico_3d(caixa, x, y, z)
                    st.plotly_chart(figura_grafico, use_container_width=True)
            
            if custo_total_jpy > 0:
                st.info(f"**Custo Total Estimado ({mod}): ¥ {custo_total_jpy:,.0f}**")
        
        st.write("---")
