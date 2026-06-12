import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
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
    if modalidade == 'ePacket': 
        return (x + y + z) <= 900 and peso <= 2000
    elif modalidade == 'Air Parcel': 
        return (x + 2 * (y + z)) <= 2000 and peso <= 30000
    elif modalidade == 'EMS': 
        return (x + 2 * (y + z)) <= 3000 and peso <= 30000
    return False

def estimar_frete_jpy(modalidade, peso_g):
    """
    Algoritmo de escalonamento oficial do Japan Post (América do Sul - Zona 5).
    Substitui tabelas estáticas por cálculo matemático de degraus via math.ceil.
    """
    if peso_g == 0: return 0
        
    if modalidade == 'ePacket':
        if peso_g > 2000: return None
        if peso_g <= 100: return 840
        # Sobe 190 ienes a cada 100g adicionais
        degraus = math.ceil((peso_g - 100) / 100)
        return 840 + (degraus * 190)
            
    elif modalidade == 'Air Parcel':
        if peso_g > 30000: return None
        if peso_g <= 1000:
            return 4550
        elif peso_g <= 10000:
            # Sobe 2700 ienes a cada 1kg
            kg_extra = math.ceil((peso_g - 1000) / 1000)
            return 4550 + (kg_extra * 2700)
        else:
            # Acima de 10kg, sobe 1800 ienes a cada 1kg
            kg_extra = math.ceil((peso_g - 10000) / 1000)
            return 28850 + (kg_extra * 1800)
        
    elif modalidade == 'EMS':
        if peso_g > 30000: return None
        if peso_g <= 500:
            return 3600
        elif peso_g <= 2000:
            # Sobe 300 ienes a cada 100g
            degraus = math.ceil((peso_g - 500) / 100)
            return 3600 + (degraus * 300)
        elif peso_g <= 6000:
            # Sobe 1500 ienes a cada 500g
            degraus = math.ceil((peso_g - 2000) / 500)
            return 8100 + (degraus * 1500)
        else:
            # Acima de 6kg, sobe 2400 ienes a cada 1kg
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
                return f"❌ O item '{item['nome']}' excede os limites de volume ou peso do {modalidade} mesmo sozinho!"
    return caixas

# --- LÓGICA VISUAL (GRÁFICOS) ---
def gerar_grafico_caixa(caixa_itens, x_caixa, y_caixa, z_caixa):
    fig, (ax_top, ax_front, ax_side) = plt.subplots(1, 3, figsize=(12, 4))
    pos_x_atual = 0
    cores = ['#FF9999', '#66B2FF', '#99FF99', '#FFCC99', '#FF99CC', '#E0E0E0', '#B266FF']
    
    for i, item in enumerate(caixa_itens):
        cor = cores[i % len(cores)]
        nome = item['nome']
        
        rect_top = patches.Rectangle((pos_x_atual, 0), item['x'], item['y'], linewidth=1, edgecolor='black', facecolor=cor, alpha=0.8)
        ax_top.add_patch(rect_top)
        ax_top.text(pos_x_atual + item['x']/2, item['y']/2, nome, ha='center', va='center', fontsize=8, rotation=90 if item['x'] < 40 else 0)
        
        rect_front = patches.Rectangle((pos_x_atual, 0), item['x'], item['z'], linewidth=1, edgecolor='black', facecolor=cor, alpha=0.8)
        ax_front.add_patch(rect_front)
        ax_front.text(pos_x_atual + item['x']/2, item['z']/2, nome, ha='center', va='center', fontsize=8, rotation=90 if item['x'] < 40 else 0)
        
        pos_x_atual += item['x']
        
    itens_ordenados_area = sorted(caixa_itens, key=lambda i: i['y']*i['z'], reverse=True)
    for item in itens_ordenados_area:
        cor = cores[caixa_itens.index(item) % len(cores)]
        rect_side = patches.Rectangle((0, 0), item['y'], item['z'], linewidth=1, edgecolor='black', facecolor=cor, alpha=0.5)
        ax_side.add_patch(rect_side)
        ax_side.text(item['y']/2, item['z']/2, item['nome'], ha='center', va='center', fontsize=8)

    for ax, title, max_x, max_y in zip(
        [ax_top, ax_front, ax_side], 
        ['Top View (X-Y)', 'Front View (X-Z)', 'Side View (Y-Z)'],
        [x_caixa, x_caixa, y_caixa],
        [y_caixa, z_caixa, z_caixa]
    ):
        ax.set_title(title)
        ax.set_xlim(0, max_x * 1.1)
        ax.set_ylim(0, max_y * 1.1)
        caixa_exterior = patches.Rectangle((0, 0), max_x, max_y, linewidth=2, edgecolor='red', facecolor='none', linestyle='--')
        ax.add_patch(caixa_exterior)

    plt.tight_layout()
    return fig

# --- INTERFACE VISUAL DO APLICATIVO ---
st.set_page_config(page_title="Calculadora de Frete", page_icon="📦", layout="wide")
st.title("📦 Calculadora de Envios Internacionais")
st.write("Digite o nome, as dimensões (em mm) e o peso (em gramas). O algoritmo calculará o valor exato segundo a tabela do Japan Post (América do Sul).")

num_figures = st.number_input("Quantos itens você vai enviar?", min_value=1, max_value=15, value=1)

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
                    st.write(f"**Dimensões da Caixa:** X={x}mm, Y={y}mm, Z={z}mm | Volumetria: {volumetria}mm")
                    
                    figura_grafico = gerar_grafico_caixa(caixa, x, y, z)
                    st.pyplot(figura_grafico)
            
            if custo_total_jpy > 0:
                st.info(f"**Custo Total Estimado ({mod}): ¥ {custo_total_jpy:,.0f}**")
        
        st.write("---")
