#!/usr/bin/env python3

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description="Plot an msiPL training-loss CSV."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to training_loss.csv",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path for the PNG output.",
    )

    parser.add_argument(
        "--title",
        default="msiPL Training Loss",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_csv(input_path)

    if "loss" not in df.columns:
        raise ValueError(
            "Expected a 'loss' column. "
            f"Found: {list(df.columns)}"
        )

    plt.figure(figsize=(9, 5))

    plt.plot(
        range(1, len(df) + 1),
        df["loss"],
        linewidth=1.5,
    )

    plt.xlabel("Epoch")
    plt.ylabel("VAE Loss")
    plt.title(args.title)

    plt.grid(alpha=0.25)

    plt.tight_layout()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    plt.savefig(
        output_path,
        dpi=250,
        bbox_inches="tight",
    )

    plt.close()

    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()