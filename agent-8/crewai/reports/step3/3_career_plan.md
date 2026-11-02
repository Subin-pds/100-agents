### Assumptions Made Based on Candidate Profile ("TODOs")
* **Target Role & Level:** Mid-level to Senior Machine Learning Engineer / GenAI Engineer (L4/L5 equivalent at MAANG).
* **Target Companies:** Amazon, Google, Meta, Microsoft, Apple (focusing heavily on Amazon and Apple given current open roles in Seattle/SF/India).
* **Experience & Education:** Mid-level (approx. 3–4 years of software/AI engineering experience); Bachelor’s or Master’s in Computer Science or a quantitative field.
* **DSA & System Design Level:** Comfortable with easy/medium LeetCode; weak on hard graph/tree problems; basic system design experience but lacks distributed ML architecture practice.
* **Constraints:** 15–20 hours per week of study time; modest budget focused primarily on essential high-impact cloud certifications (AWS Certified AI Practitioner / GCP Professional ML Engineer).

---

# MAANG AI Engineering Career Plan: 12-Month Execution Roadmap

## 1. Where You Stand — Strengths vs MAANG Requirements

| Skill / Requirement | Required by MAANG | Your Level | Gap Size |
| :--- | :--- | :--- | :--- |
| **Python / C++ / Java Programming** | High (100% of specs) | Strong Python; No C++/Java mentioned | **Medium** (Need production Python optimization/concurrency) |
| **Deep Learning & Neural Networks** | High (~91% of roles) | Basic / TODO | **High** (Need training loops, loss functions, optimization) |
| **LLMs, RAG, Agentic Workflows & MCP** | High (~82% of roles) | Advanced (Built 8 agents, MCP servers) | **Low** (Strong asset, differentiate with enterprise scale) |
| **Distributed Systems & Cloud Infra** | High (~73% of roles) | Basic (AZ-900) | **High** (Need AWS/GCP SageMaker, orchestration) |
| **Model Optimization & Inference** | High (64% of Scientist/Sr roles) | Zero exposure | **High** (Need quantization, distillation, vLLM/TensorRT-LLM) |
| **DSA & Interview Coding** | Universal gatekeeper | TODO (Medium comfort) | **Medium/High** (Needs rigorous LeetCode Med/Hard sprint) |
| **ML/System Design** | Universal for L4/L5 | TODO | **High** (Need distributed RAG, agent swarm architecture) |

---

## 2. What to Learn — Top 5 Skills/Technologies Ranked by Impact

1. **Model Optimization & Efficient Inference (vLLM, Quantization, Speculative Decoding)**
   * *Why:* Per market trends, Big Tech demands engineers who understand low-latency inference serving and cost reduction, not just API wrappers.
   * *Concrete Resource:* [Hugging Face LLM Course (Inference section)](https://huggingface.co/docs/text-generation-inference) and vLLM documentation.
2. **Advanced Distributed Cloud ML Infrastructure (AWS SageMaker, Ray, Docker/K8s)**
   * *Why:* ~73% of roles require distributed systems and cloud orchestration. Moving from local Docker to cloud-native scaling is a core MAANG requirement.
   * *Concrete Resource:* AWS Machine Learning University / Google Cloud Professional ML Engineer learning path.
3. **Deterministic Agent Tracing & Automated Evaluation Pipelines**
   * *Why:* 2026 industry standards mandate automated CI/CD evaluation and deterministic tracing for multi-step agent paths instead of manual prompting.
   * *Concrete Resource:* LangSmith / Phoenix (Arize) tracing tutorials and DeepEval / Promptfoo for CI/CD eval matrices.
4. **Data Structures & Algorithms (Graph, Dynamic Programming, Trees)**
   * *Why:* The universal filter for getting past the initial MAANG recruiter screen and technical phone screen.
   * *Concrete Resource:* NeetCode 150 (focused on patterns).
5. **Advanced Deep Learning Fundamentals (PyTorch Training Loops & Fine-Tuning)**
   * *Why:* Bridges the gap between pure API caller and Applied Scientist/ML Engineer, enabling custom LoRA/QLoRA fine-tuning.
   * *Concrete Resource:* PyTorch official tutorials & Andrej Karpathy's "Neural Networks: Zero to Hero".

---

## 3. Certifications — Which to Take, Which to Skip

* **Take:** **AWS Certified AI Practitioner** or **Google Cloud Professional Machine Learning Engineer**. 
  * *Why:* Per market reports, cloud-native GenAI specializations retain the highest market recognition among hiring managers for validating cloud-AI scale architecture.
* **Take:** **Microsoft Azure AI-102** (if targeting Azure-heavy enterprise stacks).
  * *Why:* Valued for enterprise integration tracks involving cognitive services and orchestrators.
* **Skip:** Basic fundamental certs like AZ-900 or basic AI badges without rigorous proctored labs. 
  * *Why:* MAANG interviewers discount basic theoretical certificates; they care exclusively about production systems you've built and scaled.

---

## 4. Portfolio — Upcoming Agents to Build (Closing the Gaps)

Since you have already built 8 foundational agents (including raw ReAct, MCP servers, and Twilio voice apps), your next 3 portfolio projects must target **Enterprise Scale, Observability, and Model Optimization**:

1. **Agent #9: Enterprise Multi-Agent Swarm with A2A Protocol & MCP**
   * *What to build:* A multi-agent negotiation system (using Anthropic Claude / GPT-6.1) communicating via Model Context Protocol (MCP) standards with role-based access control and sandboxed tool execution.
   * *Gap closed:* Standardized interoperability and secure agentic workflows.
2. **Agent #10: Production-Grade RAG with Automated CI/CD Evaluation & Tracing**
   * *What to build:* A hybrid-search RAG pipeline integrated with Phoenix/LangSmith tracing and an automated DeepEval testing matrix running in GitHub Actions for hallucination and latency regression.
   * *Gap closed:* Automated evaluation pipelines and deterministic agent tracing.
3. **Agent #11: Quantized Open-Source LLM Serving Pipeline (vLLM + LoRA Fine-Tuning)**
   * *What to build:* Fine-tune an open model (e.g., Llama-3/Mistral) using QLoRA on a domain dataset, deploy it locally/cloud using vLLM, and optimize inference latency with INT4 quantization.
   * *Gap closed:* Model optimization, efficient inference, and PyTorch fundamentals.

---

## 5. Interview Prep Blueprint

* **DSA (Coding):** 
  * Commit to 5 LeetCode problems per week using the NeetCode 150 framework. Focus heavily on Arrays, Strings, Trees, Graphs, and Dynamic Programming. Practice talking through your optimal solutions out loud.
* **System Design (General Infrastructure):** 
  * Master large-scale distributed systems concepts: load balancing, caching (Redis), sharding, rate limiting, and database consistency models.
* **ML Design / GenAI Architecture:** 
  * Prepare to design systems like: *Design a Real-Time Enterprise RAG System with Low Latency*, *Design a Scalable Multi-Agent Customer Support Platform*, and *Design a Guardrail System for Prompt Injection Defense*.
* **Behavioural (Leadership Principles):** 
  * Map your 11 portfolio projects and past work experience to Amazon's Leadership Principles (Customer Obsession, Ownership, Bias for Action) or Google's "Googleyness & Leadership" rubric using the STAR method.

---

## 6. 12-Month Roadmap (Quarter by Quarter)

### Q1 (Months 1–3): Fundamentals & Core Agent Scaling
* **Focus:** Master PyTorch training loops, bridge Deep Learning gaps, and solve 40 LeetCode problems (Easy/Medium).
* **Projects:** Build **Agent #9 (Enterprise Multi-Agent Swarm with MCP)**.
* **Milestone:** Complete NeetCode Arrays/Strings/Trees; successfully run a multi-agent system with MCP transport security.

### Q2 (Months 4–6): Cloud Infrastructure & Observability
* **Focus:** Study for and pass **AWS Certified AI Practitioner** / **Google Cloud Professional ML Engineer**. Learn distributed system design.
* **Projects:** Build **Agent #10 (Production-Grade RAG with CI/CD Eval)**.
* **Milestone:** Pass cloud certification; implement automated evaluation suites running in GitHub Actions.

### Q3 (Months 7–9): Model Optimization & Advanced System Design
* **Focus:** Master vLLM, quantization, and model distillation. Solve another 40 LeetCode problems (Graph, DP).
* **Projects:** Build **Agent #11 (Quantized Open-Source LLM Serving Pipeline)**.
* **Milestone:** Successfully fine-tune and serve a quantized model with sub-100ms time-to-first-token.

### Q4 (Months 10–12): Mock Interviews, Polish & Application Sprint
* **Focus:** Conduct weekly mock interviews (Pramp / Interviewing.io). Refine resume highlighting agentic architectures and production scale. Apply directly to MAANG AI engineering roles (Amazon, Apple, Google).
* **Projects:** Final polish of GitHub portfolio READMEs and system architecture diagrams.
* **Milestone:** Clear recruiter screens, pass technical phone screens, and secure on-site loops at target MAANG companies.

---

## 7. This Week — 3 Concrete Actions

1. **Audit & Setup LeetCode Schedule:** Open NeetCode 150, bookmark the first 10 array/string problems, and schedule 45 minutes every morning for coding practice.
2. **Initiate Agent #9 Architecture:** Draft the system architecture for your multi-agent swarm using Anthropic Claude and Model Context Protocol (MCP) transport standards.
3. **Register for Cloud Certification:** Select your test date for the AWS Certified AI Practitioner or Google Cloud Professional ML Engineer exam to lock in accountability.