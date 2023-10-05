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

    // Financial data examples
    { text: "Which product generated the highest revenue?", value: "Which product generated the highest revenue?" },
    { text: "Which lowest performing department", value: "Which lowest performing department" },
    {
        text: "What can you say about Departmental Interactions and Budget Allocation",
        value: "What can you say about Departmental Interactions and Budget Allocation"
    }
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
