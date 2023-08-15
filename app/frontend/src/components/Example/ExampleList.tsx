import { Example } from "./Example";

import styles from "./Example.module.css";

export type ExampleModel = {
    text: string;
    value: string;
};

const EXAMPLES: ExampleModel[] = [
    // Employee hand book examples
    // {
    //     text: "What is included in my Northwind Health Plus plan that is not in standard?",
    //     value: "What is included in my Northwind Health Plus plan that is not in standard?"
    // },
    // { text: "What happens in a performance review?", value: "What happens in a performance review?"},
    // { text: "What does a Product Manager do?", value: "What does a Product Manager do?"},

    // Real Estate data examples
    { text: "Which was the most valuable interior remodeling?", value: "Which was the most valuable interior remodeling?" },
    { text: "Which years did the housing market take a hit?", value: "Which years did the housing market take a hit?" },
    {
        text: "What's Redfin's opinion about home-flippers in Jun-2022",
        value: "What's Redfin's opinion about home-flippers in Jun-2022"
    },
    { text: "Which state had biggest change in inventory levels?", value: "Which state had biggest change in inventory levels?" }
];

interface Props {
    onExampleClicked: (value: string) => void;
}

export const ExampleList = ({ onExampleClicked }: Props) => {
    return (
        <ul className={styles.examplesNavList}>
            {EXAMPLES.map((x, i) => (
                <li key={i}>
                    <Example text={x.text} value={x.value} onClick={onExampleClicked} />
                </li>
            ))}
        </ul>
    );
};
