"""Run the facility-location idea from submodular_efficient_(1).py on a CSV."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "sourcecode" / "src"))
import pandas as pd
from vx.com.py.sampling.Submodular import shortlist


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--size", required=True, type=int)
    parser.add_argument("--target", help="Column to exclude from selection distances")
    parser.add_argument("--axis", choices=("rows", "features"), default="rows")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must be different files")
    frame = pd.read_csv(args.input)
    features = frame.drop(columns=[args.target]) if args.target else frame
    vectors = features.to_numpy(dtype=float)
    ids = shortlist(vectors if args.axis == "rows" else vectors.T,
                    args.size, random_state=args.seed)
    if args.axis == "rows":
        result = frame.iloc[ids]
    else:
        columns = features.columns[ids].tolist()
        if args.target:
            columns.append(args.target)
        result = frame.loc[:, columns]
    result.to_csv(args.output, index=False)
    print("Selected {} {} -> {}".format(len(ids), args.axis, args.output))


if __name__ == "__main__":
    main()
