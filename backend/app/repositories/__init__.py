"""Repository layer — data-access objects for each domain table."""

from app.repositories.base import BaseRepository
from app.repositories.discussion_repository import DiscussionRepository
from app.repositories.expert_repository import ExpertRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.repositories.consensus_repository import ConsensusRepository
from app.repositories.divergence_repository import DivergenceRepository

__all__ = [
    "BaseRepository",
    "DiscussionRepository",
    "ExpertRepository",
    "TranscriptRepository",
    "ConsensusRepository",
    "DivergenceRepository",
]
