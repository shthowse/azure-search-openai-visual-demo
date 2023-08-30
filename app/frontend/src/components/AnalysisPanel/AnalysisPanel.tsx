import { Stack, Pivot, PivotItem } from "@fluentui/react";
import SyntaxHighlighter from "react-syntax-highlighter";

import styles from "./AnalysisPanel.module.css";

import { SupportingContent } from "../SupportingContent";
import { AskResponse } from "../../api";
import { AnalysisPanelTabs } from "./AnalysisPanelTabs";

interface Props {
    className: string;
    activeTab: AnalysisPanelTabs;
    onActiveTabChanged: (tab: AnalysisPanelTabs) => void;
    activeCitation: string | undefined;
    citationHeight: string;
    answer: AskResponse;
}

const pivotItemDisabledStyle = { disabled: true, style: { color: "grey" } };

export const AnalysisPanel = ({ answer, activeTab, activeCitation, citationHeight, className, onActiveTabChanged }: Props) => {
    const isDisabledThoughtProcessTab: boolean = !answer.thought_steps;
    const isDisabledSupportingContentTab: boolean = !answer.data_points;
    const isDisabledCitationTab: boolean = !activeCitation;

    return (
        <Pivot
            className={className}
            selectedKey={activeTab}
            onLinkClick={pivotItem => pivotItem && onActiveTabChanged(pivotItem.props.itemKey! as AnalysisPanelTabs)}
        >
            <PivotItem
                itemKey={AnalysisPanelTabs.ThoughtProcessTab}
                headerText="Thought process"
                headerButtonProps={isDisabledThoughtProcessTab ? pivotItemDisabledStyle : undefined}
            >
                <div>
                    <ul className={styles.tList}>
                        {answer.thought_steps.map(t => {
                            return (
                                <li className={styles.tListItem}>
                                    <div className={styles.tStep}>{t.title}</div>
                                    {Array.isArray(t.description) ? (
                                        <SyntaxHighlighter language="json" wrapLongLines className={styles.tCodeBlock}>
                                            {JSON.stringify(t.description, null, 2)}
                                        </SyntaxHighlighter>
                                    ) : (
                                        <>
                                            <div>{t.description}</div>
                                            <Stack horizontal tokens={{ childrenGap: 5 }}>
                                                {t.props &&
                                                    (Object.keys(t.props) || []).map((k: any) => (
                                                        <span className={styles.tProp}>
                                                            {k}: {JSON.stringify(t.props?.[k])}
                                                        </span>
                                                    ))}
                                            </Stack>
                                        </>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                </div>
            </PivotItem>
            <PivotItem
                itemKey={AnalysisPanelTabs.SupportingContentTab}
                headerText="Supporting content"
                headerButtonProps={isDisabledSupportingContentTab ? pivotItemDisabledStyle : undefined}
            >
                <SupportingContent supportingContent={answer.data_points} />
            </PivotItem>
            <PivotItem
                itemKey={AnalysisPanelTabs.CitationTab}
                headerText="Citation"
                headerButtonProps={isDisabledCitationTab ? pivotItemDisabledStyle : undefined}
            >
                {activeCitation?.endsWith(".png") ? (
                    <img src={activeCitation} className={styles.citationImg} />
                ) : (
                    <iframe title="Citation" src={activeCitation} width="100%" height={citationHeight} />
                )}
            </PivotItem>
        </Pivot>
    );
};
