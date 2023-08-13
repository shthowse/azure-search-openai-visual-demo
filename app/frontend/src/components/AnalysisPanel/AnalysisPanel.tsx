import { Icon, Pivot, PivotItem,   } from "@fluentui/react";
 import SyntaxHighlighter from "react-syntax-highlighter";

import styles from "./AnalysisPanel.module.css";

import { SupportingContent } from "../SupportingContent";
import { AskResponse, Thoughts } from "../../api";
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
    const isDisabledThoughtProcessTab: boolean = !answer.thoughtSteps;
    const isDisabledSupportingContentTab: boolean = !answer.data_points.length;
    const isDisabledCitationTab: boolean = !activeCitation;

    const thoughtSteps = answer.thoughtSteps as Thoughts[];

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
                {/* <div className={styles.thoughtProcess} dangerouslySetInnerHTML={{ __html: sanitizedThoughts }}></div> */}
                <div>
                    <ul className={styles.tList}>
                        {thoughtSteps.map(t => {
                            return (
                                <li className={styles.tListItem}>
                                    <div className={styles.tStep}>{t.title}</div>
                                    {Array.isArray(t.description) ? (
                                        <SyntaxHighlighter language="json" wrapLongLines className={styles.tCodeBlock}>
                                            {JSON.stringify(t.description, null, 2)}
                                        </SyntaxHighlighter>
                                    ) : (
                                        <div className="item-title">{t.description}</div>
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
                <iframe title="Citation" src={activeCitation} width="100%" height={citationHeight} />
            </PivotItem>
        </Pivot>
    );
};
