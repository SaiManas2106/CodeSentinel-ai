"""Fine-tune CodeLlama with QLoRA for code review tasks."""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
import mlflow
import wandb
from datasets import Dataset, concatenate_datasets, load_dataset
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    TrainingArguments,
)
from trl import SFTTrainer


@dataclass
class TrainConfig:
    model_name: str
    output_dir: str
    max_steps: int
    eval_steps: int
    save_steps: int
    learning_rate: float
    per_device_train_batch_size: int
    gradient_accumulation_steps: int
    mlflow_tracking_uri: str
    wandb_project: str
    wandb_entity: str
    s3_bucket: str


def format_instruction(example: dict[str, Any]) -> dict[str, str]:
    """Format dataset row into instruction tuning format."""
    code = example.get("code") or example.get("func") or ""
    target = example.get("docstring") or example.get("target") or example.get("vulnerability") or "Provide review feedback."
    prompt = {
        "instruction": "Review this code",
        "input": code,
        "output": str(target),
    }
    text = f"### Instruction\n{prompt['instruction']}\n\n### Input\n{prompt['input']}\n\n### Output\n{prompt['output']}"
    return {"text": text}


def upload_checkpoint_to_s3(checkpoint_dir: Path, bucket: str, prefix: str = "checkpoints") -> None:
    """Upload local checkpoint directory to S3."""
    s3 = boto3.client("s3")
    for file in checkpoint_dir.rglob("*"):
        if file.is_file():
            key = f"{prefix}/{checkpoint_dir.name}/{file.relative_to(checkpoint_dir).as_posix()}"
            s3.upload_file(str(file), bucket, key)


def build_dataset() -> Dataset:
    """Load and build combined instruction tuning dataset."""
    codesearchnet = load_dataset("code_search_net", "python", split="train[:2%]")
    bigvul = load_dataset("adithya8/BigVul", split="train[:20%]")

    cs = codesearchnet.map(lambda x: {"code": x.get("whole_func_string", ""), "target": x.get("func_documentation_string", "")})
    bv = bigvul.map(lambda x: {"code": x.get("func_before", ""), "target": x.get("vul", "")})

    merged = concatenate_datasets([cs, bv]).map(format_instruction, remove_columns=[c for c in cs.column_names if c in cs.column_names])
    return merged.train_test_split(test_size=0.1, seed=42)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune CodeLlama-13B with QLoRA")
    parser.add_argument("--model-name", default="codellama/CodeLlama-13b-Instruct-hf")
    parser.add_argument("--output-dir", default="./artifacts/codellama-lora")
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--eval-steps", type=int, default=50)
    parser.add_argument("--save-steps", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--grad-accumulation", type=int, default=8)
    parser.add_argument("--mlflow-tracking-uri", required=True)
    parser.add_argument("--wandb-project", required=True)
    parser.add_argument("--wandb-entity", required=True)
    parser.add_argument("--s3-bucket", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = TrainConfig(
        model_name=args.model_name,
        output_dir=args.output_dir,
        max_steps=args.max_steps,
        eval_steps=args.eval_steps,
        save_steps=args.save_steps,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accumulation,
        mlflow_tracking_uri=args.mlflow_tracking_uri,
        wandb_project=args.wandb_project,
        wandb_entity=args.wandb_entity,
        s3_bucket=args.s3_bucket,
    )

    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    mlflow.set_experiment("codesentinel-codellama-qlora")
    wandb.init(project=cfg.wandb_project, entity=cfg.wandb_entity, config=vars(cfg))

    with mlflow.start_run(run_name="codellama-13b-qlora"):
        dataset_split = build_dataset()
        tokenizer = AutoTokenizer.from_pretrained(cfg.model_name, use_fast=True)
        tokenizer.pad_token = tokenizer.eos_token

        quant_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype="bfloat16", bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
        model = AutoModelForCausalLM.from_pretrained(cfg.model_name, quantization_config=quant_config, device_map="auto")

        lora_config = LoraConfig(
            r=64,
            lora_alpha=16,
            lora_dropout=0.1,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)

        train_args = TrainingArguments(
            output_dir=cfg.output_dir,
            bf16=True,
            gradient_checkpointing=True,
            per_device_train_batch_size=cfg.per_device_train_batch_size,
            gradient_accumulation_steps=cfg.gradient_accumulation_steps,
            learning_rate=cfg.learning_rate,
            max_steps=cfg.max_steps,
            logging_steps=10,
            save_steps=cfg.save_steps,
            eval_steps=cfg.eval_steps,
            evaluation_strategy="steps",
            report_to=["wandb"],
            save_total_limit=3,
        )

        trainer = SFTTrainer(
            model=model,
            train_dataset=dataset_split["train"],
            eval_dataset=dataset_split["test"],
            dataset_text_field="text",
            tokenizer=tokenizer,
            args=train_args,
            data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
        )

        trainer.train()
        eval_metrics = trainer.evaluate()
        for key, value in eval_metrics.items():
            if isinstance(value, (int, float)):
                mlflow.log_metric(key, value)

        trainer.save_model(cfg.output_dir)
        adapter_model = PeftModel.from_pretrained(model, cfg.output_dir)
        merged_model = adapter_model.merge_and_unload()
        merged_output = Path(cfg.output_dir) / "merged"
        merged_model.save_pretrained(merged_output)
        tokenizer.save_pretrained(merged_output)

        for checkpoint in Path(cfg.output_dir).glob("checkpoint-*"):
            upload_checkpoint_to_s3(checkpoint, cfg.s3_bucket)

        mlflow.log_params(vars(cfg))
        mlflow.log_artifacts(str(merged_output), artifact_path="final_model")

    wandb.finish()


if __name__ == "__main__":
    main()
