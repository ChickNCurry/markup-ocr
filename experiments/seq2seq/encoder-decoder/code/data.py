import pickle
from typing import Callable, List, Tuple
import os
import cv2
import torch
from torch import Tensor
from torch.utils.data import Dataset  # type: ignore
from torch.nn.functional import pad
from torch.nn.utils.rnn import pad_sequence
from torchvision import transforms  # type: ignore
from transformers import PreTrainedTokenizerFast  # type: ignore
from tokenizers import Tokenizer, models, pre_tokenizers, trainers  # type: ignore


def create_tokenizer(
    equations_path: str, tokenizer_path: str
) -> PreTrainedTokenizerFast:
    equations = []

    with open(equations_path, "r") as file:
        equations = file.readlines()

    tokenizer = Tokenizer(models.BPE())
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.add_special_tokens(["[BOS]", "[PAD]", "[EOS]"])

    trainer = trainers.BpeTrainer(special_tokens=["[PAD]", "[BOS]", "[EOS]"])
    tokenizer.train_from_iterator(equations, trainer=trainer)

    tokenizer.save(tokenizer_path)


def load_tokenizer(tokenizer_path: str) -> PreTrainedTokenizerFast:
    return PreTrainedTokenizerFast(tokenizer_file=tokenizer_path)


def clean(text: str) -> str:
    strs_to_clean = ["Ġ", "Ċ", "[PAD]", "[BOS]", "[EOS]"]
    for s in strs_to_clean:
        text = text.replace(s, " ")
    return text.strip()


def create_img_names_to_skip(img_dir: str, img_names_to_skip_dir: str) -> None:
    img_names = os.listdir(img_dir)

    img_names_to_skip = []

    for img_name in img_names:
        try:
            img = cv2.imread(os.path.join(img_dir, img_name), cv2.IMREAD_GRAYSCALE)
            transforms.Compose([transforms.ToTensor()])(img)
        except:
            img_names_to_skip.append(img_name)

    with open(img_names_to_skip_dir, "wb") as file:
        pickle.dump(img_names_to_skip, file)


def load_img_names_to_skip(img_names_to_skip_dir: str) -> List[str]:
    with open(img_names_to_skip_dir, "rb") as file:
        img_names_to_skip: List[str] = pickle.load(file)

    return img_names_to_skip


def get_img_dims(img_path: str) -> Tuple[int, ...]:
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    return img.shape


class LatexEquationDataset(Dataset):  # type: ignore
    def __init__(
        self,
        equations_path: str,
        img_dir: str,
        img_names_to_skip: List[str],
        tokenizer: PreTrainedTokenizerFast,
    ):
        super().__init__()

        with open(equations_path, "r") as file:
            self._equations = file.readlines()

        self._img_dir = img_dir
        self._img_names = [x for x in os.listdir(img_dir) if x not in img_names_to_skip]

        # img_names_dims = [
        #     (img_name, get_img_dims(os.path.join(img_dir, img_name)))
        #     for img_name in self._img_names
        # ]
        # self._img_names = [
        #     x[0]
        #     for x in sorted(
        #         img_names_dims, key=lambda x: x[1][0] * x[1][1], reverse=True
        #     )
        # ]

        self.transform = transforms.Compose([transforms.ToTensor()])
        self.tokenizer = tokenizer

    def __len__(self) -> int:
        return len(self._img_names)

    def __getitem__(self, idx: int) -> Tuple[Tensor, Tensor]:
        img_name = self._img_names[idx]
        img = cv2.imread(os.path.join(self._img_dir, img_name), cv2.IMREAD_GRAYSCALE)
        img_tensor = self.transform(img)

        eq_idx = int(img_name.split(".")[0])
        equation = self._equations[eq_idx]
        token_ids = torch.tensor(self.tokenizer.encode(equation), dtype=torch.int64)

        return img_tensor, token_ids


def get_input_token_ids(
    token_ids: Tensor, tokenizer: PreTrainedTokenizerFast
) -> Tensor:
    return torch.cat(
        [
            torch.tensor(
                [tokenizer.convert_tokens_to_ids("[BOS]")], dtype=torch.int64
            ).expand(10, 1),
            token_ids,
        ],
        dim=1,
    )


def get_target_token_ids(
    token_ids: Tensor, tokenizer: PreTrainedTokenizerFast
) -> Tensor:
    return torch.cat(
        [
            token_ids,
            torch.tensor(
                [tokenizer.convert_tokens_to_ids("[EOS]")], dtype=torch.int64
            ).expand(10, 1),
        ],
        dim=1,
    )


def curry_collate_fn(
    padding_token_id: int, img_padding_value: float = 1
) -> Callable[[List[Tuple[Tensor, Tensor]]], Tuple[Tensor, Tensor]]:

    def collate_fn(batch: List[Tuple[Tensor, Tensor]]) -> Tuple[Tensor, Tensor]:
        imgs = [entry[0] for entry in batch]
        equations = [entry[1] for entry in batch]

        max_h = max(img.shape[1] for img in imgs)
        max_w = max(img.shape[2] for img in imgs)

        padded_imgs = [
            pad(
                img,
                (0, max_w - img.shape[2], 0, max_h - img.shape[1]),
                value=img_padding_value,
            )
            for img in imgs
        ]

        padded_equations = pad_sequence(
            equations, batch_first=True, padding_value=padding_token_id
        )

        return torch.stack(padded_imgs), padded_equations

    return collate_fn
