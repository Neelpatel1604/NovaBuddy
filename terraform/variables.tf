variable "project_name" {
  description = "Project name prefix for all resources"
  type        = string
  default     = "novabuddy"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "model_id" {
  description = "Bedrock model ID for reasoning"
  type        = string
  default     = "amazon.nova-lite-v1:0"
}

variable "embedding_model_id" {
  description = "Bedrock model ID for multimodal embeddings (stretch goal)"
  type        = string
  default     = "amazon.nova-embed-multimodal-v1:0"
}
