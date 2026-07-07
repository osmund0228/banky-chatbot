"""
LLM 엔진 (모델 공유)
- Qwen 모델 하나를 로드해서, 서식 추출과 상담 RAG가 함께 사용한다.
- 코랩 GPU 메모리 절약의 핵심: 모델을 한 번만 올린다.
- transformers 기반. 텍스트 생성 단일 진입점(generate)을 제공.

사용 예 (코랩):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct", ...)
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct")
    engine = LLMEngine(model, tokenizer)

    # 서식 추출기와 상담 RAG에 같은 engine을 주입
    extractor = HFSlotExtractor(engine=engine)
    consultant = ConsultRAG(engine=engine, ...)
"""
from __future__ import annotations


class LLMEngine:
    """Qwen 모델 1개를 감싸는 공유 엔진."""

    def __init__(self, model, tokenizer, default_max_new_tokens: int = 512):
        self.model = model
        self.tokenizer = tokenizer
        self.default_max_new_tokens = default_max_new_tokens

    def generate(self, messages, temperature: float = 0.0,
                 max_new_tokens: int | None = None,
                 top_p: float | None = None,
                 repetition_penalty: float | None = None) -> str:
        """채팅 메시지 리스트 -> 생성된 텍스트.

        messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
        top_p, repetition_penalty: 지정 시에만 전달(미지정이면 기존 동작 유지).
          상담 RAG는 원본 BankySession과 동일하게 top_p=0.9, repetition_penalty=1.15
          를 넘겨 검증된 생성 품질을 재현한다. 서식 추출(1·2번)은 안 넘기므로 영향 없음.
        """
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        gen_kwargs = {
            "max_new_tokens": max_new_tokens or self.default_max_new_tokens,
            "do_sample": temperature > 0,
        }
        if temperature > 0:
            gen_kwargs["temperature"] = temperature
        if top_p is not None:
            gen_kwargs["top_p"] = top_p
        if repetition_penalty is not None:
            gen_kwargs["repetition_penalty"] = repetition_penalty
        out = self.model.generate(**inputs, **gen_kwargs)
        gen = out[0][inputs.input_ids.shape[1]:]
        return self.tokenizer.decode(gen, skip_special_tokens=True).strip()
