## 5 puntos clave para optimizar Claude Code y modelos de IA locales

### 1. La expertise de dominio supera el prompting genérico
Los LLMs recompensan la profundidad técnica en el dominio que estás usando; un buen conocimiento del código o el problema convierte al LLM en un "colaborador" que no requiere que le expliquemos todo desde cero.

**Verificado en:** [LLMs reward expertise](https://www.seangoedecke.com/llms-reward-expertise/)

---

### 2. Entrena razonamiento con RL, no solo con supervisión
Para tareas complejas (código, matemáticas, razonamiento lógico), el aprendizaje por refuerzo libera patrones emergentes como auto-reflexión y verificación, superando al entrenamiento tradicional con pocas demostraciones humanas.

**Verificado en:** [DeepSeek-R1: Incentivizing Reasoning via RL](https://arxiv.org/abs/2501.12948)

---

### 3. Poca computación en tiempo de prueba escala mejor que muchas muestras de entrenamiento
Con modelos reforzados para pensar antes de responder, cada token "reflexivo" vale más que una masa de ejemplos; o1 demuestra que el *test-time compute* es el límite escalable, no la saturación de *train-time* muestras.

**Verificado en:** [Learning to Reason with LLMs](https://openai.com/index/learning-to-reason-with-llms/)

---

### 4. El futuro es inevitable, pero las muestras son tóxicas
Evita el inevitabilismo ciego (aceptar que todo modelado será así) y acepta que con solo unas pocas muestras bien elegidas puedes "envenenar" o calibrar cualquier modelo, incluso de gran escala.

**Verificado en:** [A small number of samples can poison LLMs](https://www.anthropic.com/research/small-samples-poison)

---

### 5. Visualiza, compara y combina los sistemas
La claridad de los arquitecturas (especialmente con *speculative decoding* y *chain-of-thought* interno) y las curvas de *pass@1* en benchmarks revelan dónde invertir: modelos con *reasoning time* separado del *output* y subagentes que delegan su *thinking* a modelos más lentos.

**Verificado en:** [LLM Visualization](https://bbycroft.net/llm)
